"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { CrisisScreen } from "@/components/calma/crisis-screen";
import { ProgressBar } from "@/components/calma/progress-bar";
import { QuestionCard } from "@/components/calma/question-card";
import { api, guestStore, type Context, type Questionnaire, type Result } from "@/lib/api";
import { ITEM_COUNTS, answersFor, buildScreens, screenKey, sumAnswers, type QuestionnaireId } from "@/lib/flow";

const QIDS: QuestionnaireId[] = ["gad2", "gad7", "phq9", "oasis"];
const AGE_BANDS = ["18-24", "25-34", "35-44", "45-54", "55-64", "65+"];
const GENDERS = ["female", "male", "non_binary", "other", "prefer_not"] as const;
const DURATIONS = ["<2w", "2w-1m", "1-6m", "6m+"] as const;
const FLOW_KEY = "calma.flow";

type FlowState = {
  sessionId: string | null;
  idx: number;
  answers: Record<string, number>;
  timings: Record<string, number>;
  wantsFull: boolean;
  context: Context;
};
const EMPTY: FlowState = { sessionId: null, idx: 0, answers: {}, timings: {}, wantsFull: false, context: {} };

function loadFlow(): FlowState {
  try {
    return { ...EMPTY, ...JSON.parse(sessionStorage.getItem(FLOW_KEY) ?? "{}") };
  } catch {
    return EMPTY;
  }
}

const fieldClass = "min-h-12 w-full rounded-xl border border-input bg-surface px-4 text-base focus-visible:ring-[3px] focus-visible:ring-ring/50 outline-none";

export default function AssessPage() {
  const t = useTranslations("assess");
  const tc = useTranslations("common");
  const locale = useLocale();
  const router = useRouter();

  const [defs, setDefs] = useState<Partial<Record<QuestionnaireId, Questionnaire>>>({});
  const [state, setState] = useState<FlowState>(EMPTY);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "failed">("idle");
  const [submitting, setSubmitting] = useState(false);
  const [crisis, setCrisis] = useState<Result | null>(null);
  const shownAt = useRef<number>(Date.now());

  // Consent gate + resume
  useEffect(() => {
    if (!sessionStorage.getItem("calma.consent")) {
      router.replace("/consent");
      return;
    }
    setState(loadFlow());
    setLoaded(true);
  }, [router]);

  useEffect(() => {
    if (loaded) sessionStorage.setItem(FLOW_KEY, JSON.stringify(state));
  }, [state, loaded]);

  // Validated wording always comes from the API (official forms), in the chosen language.
  useEffect(() => {
    let cancelled = false;
    Promise.all(QIDS.map((q) => api.questionnaire(q, locale)))
      .then((list) => !cancelled && setDefs(Object.fromEntries(list.map((q) => [q.id, q]))))
      .catch(() => !cancelled && setError(t("loadFailed")));
    return () => {
      cancelled = true;
    };
  }, [locale, t]);

  const gad2Ids = useMemo(() => defs.gad2?.items.map((i) => i.id) ?? ["gad7_1", "gad7_2"], [defs.gad2]);
  const gad2Score = sumAnswers(state.answers, gad2Ids);
  const screens = useMemo(() => buildScreens(gad2Score, state.wantsFull), [gad2Score, state.wantsFull]);
  const idx = Math.min(state.idx, screens.length - 1);
  const screen = screens[idx];

  useEffect(() => {
    shownAt.current = Date.now();
  }, [idx]);

  const go = (delta: number) => setState((s) => ({ ...s, idx: Math.max(0, Math.min(s.idx + delta, screens.length - 1)) }));

  const save = useCallback(
    async (qid: QuestionnaireId, answers: Record<string, number>, timings: Record<string, number>) => {
      const def = defs[qid];
      if (!state.sessionId || !def) return;
      setSaveState("saving");
      try {
        await api.saveAnswers(state.sessionId, qid, answersFor(qid, def.items.map((i) => i.id), answers), timings);
        setSaveState("saved");
      } catch {
        setSaveState("failed");
      }
    },
    [defs, state.sessionId],
  );

  const onAnswer = useCallback(
    (value: number) => {
      if (screen?.kind !== "question") return;
      const def = defs[screen.qid];
      const item = def?.items[screen.index];
      if (!item) return;
      const answers = { ...state.answers, [item.id]: value };
      const timings = { ...state.timings, [item.id]: Math.round((Date.now() - shownAt.current) / 100) / 10 };
      setState((s) => ({ ...s, answers, timings }));
      void save(screen.qid, answers, timings);
      window.setTimeout(() => setState((s) => ({ ...s, idx: Math.min(s.idx + 1, buildScreens(sumAnswers(answers, gad2Ids), s.wantsFull).length - 1) })), 180);
    },
    [screen, defs, state.answers, state.timings, save, gad2Ids],
  );

  const startSession = async () => {
    setError(null);
    try {
      if (!state.sessionId) {
        const s = await api.createSession(locale, { ...state.context, language: locale as "en" | "hi", country: "IN" });
        if (s.guest_token) guestStore.rememberSession(s.id, s.guest_token);
        setState((st) => ({ ...st, sessionId: s.id, idx: st.idx + 1 }));
      } else {
        go(1);
      }
    } catch {
      setError(tc("error"));
    }
  };

  const updateContext = async (patch: Context) => {
    setState((s) => ({ ...s, context: { ...s.context, ...patch } }));
    if (state.sessionId) await api.updateContext(state.sessionId, patch).catch(() => setSaveState("failed"));
  };

  const finish = async () => {
    if (!state.sessionId) return;
    setSubmitting(true);
    setError(null);
    try {
      if (state.context.free_text || state.context.sleep_hours !== undefined) {
        await api.updateContext(state.sessionId, state.context);
      }
      const result = await api.submit(state.sessionId);
      guestStore.rememberResult(result.id, state.sessionId);
      sessionStorage.removeItem(FLOW_KEY);
      if (result.flagged && result.crisis) setCrisis(result);
      else router.push(`/results/${result.id}`);
    } catch {
      setError(tc("error"));
      setSubmitting(false);
    }
  };

  if (crisis?.crisis) {
    return <CrisisScreen helplines={crisis.crisis} onContinue={() => router.push(`/results/${crisis.id}`)} />;
  }
  if (!loaded || !screen) return <main className="mx-auto max-w-[640px] px-6 py-16">{tc("loading")}</main>;

  const questionDef = screen.kind === "question" ? defs[screen.qid] : undefined;
  const item = screen.kind === "question" ? questionDef?.items[screen.index] : undefined;
  const options = item ? (item.options ?? questionDef?.options ?? []) : [];

  return (
    <main className="mx-auto flex min-h-[80vh] max-w-[640px] flex-col gap-8 px-6 py-10">
      <div className="flex flex-col gap-2">
        <ProgressBar value={idx} max={Math.max(screens.length - 1, 1)} label={t("overall")} />
        <div className="flex min-h-6 items-center justify-between text-sm text-muted-foreground">
          {idx > 0 ? (
            <button type="button" onClick={() => go(-1)} className="min-h-10 rounded-lg px-2 hover:text-foreground">
              ← {tc("back")}
            </button>
          ) : (
            <span />
          )}
          <span aria-live="polite">{saveState === "saving" ? t("saving") : saveState === "saved" ? t("saved") : saveState === "failed" ? t("saveFailed") : ""}</span>
        </div>
      </div>

      {error && (
        <p role="alert" className="rounded-xl bg-band-severe/10 px-4 py-3 text-sm">
          {error}
        </p>
      )}

      <AnimatePresence mode="wait">
        <motion.div key={screenKey(screen)} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.2 }}>
          {screen.kind === "context" && (
            <section className="flex flex-col gap-6" aria-labelledby="ctx-title">
              <h1 id="ctx-title" className="text-3xl font-medium">
                {t("contextTitle")}
              </h1>
              <p className="text-muted-foreground">{t("contextLead")}</p>
              <fieldset className="flex flex-col gap-3">
                <legend className="mb-2 font-medium">{t("ageBand")}</legend>
                <div className="grid grid-cols-3 gap-3">
                  {AGE_BANDS.map((a) => (
                    <button
                      key={a}
                      type="button"
                      aria-pressed={state.context.age_band === a}
                      onClick={() => setState((s) => ({ ...s, context: { ...s.context, age_band: a } }))}
                      className={`min-h-12 rounded-xl border px-3 ${state.context.age_band === a ? "border-sage-deep bg-accent font-medium" : "border-border bg-surface hover:bg-accent/60"}`}
                    >
                      {a}
                    </button>
                  ))}
                </div>
              </fieldset>
              <label className="flex flex-col gap-2">
                <span className="font-medium">
                  {t("gender")} <span className="font-normal text-muted-foreground">({tc("optional")})</span>
                </span>
                <select className={fieldClass} value={state.context.gender ?? ""} onChange={(e) => setState((s) => ({ ...s, context: { ...s.context, gender: e.target.value || undefined } }))}>
                  <option value="">—</option>
                  {GENDERS.map((g) => (
                    <option key={g} value={g}>
                      {t(`genderOptions.${g}`)}
                    </option>
                  ))}
                </select>
              </label>
              <Button size="lg" className="h-12 self-start rounded-xl px-7 text-base" disabled={!state.context.age_band || !defs.gad2} onClick={startSession}>
                {tc("continue")}
              </Button>
            </section>
          )}

          {screen.kind === "question" && item && questionDef && questionDef.language !== locale && (
            <p lang={locale} className="mb-4 rounded-xl bg-muted px-4 py-2 text-sm text-muted-foreground">
              {t("englishOnly")}
            </p>
          )}
          {screen.kind === "question" && item && questionDef && (
            <QuestionCard
              timeframe={screen.index === 0 || (screen.qid === "gad7" && screen.index === 2) ? questionDef.timeframe : undefined}
              text={item.text}
              options={options}
              value={state.answers[item.id]}
              onAnswer={onAnswer}
              progressLabel={`${questionDef.name} · ${t("progress", { current: screen.index + 1, total: ITEM_COUNTS[screen.qid] })}`}
              keysHint={t("keysHint", { first: 1, last: options.length })}
            />
          )}

          {screen.kind === "low" && (
            <section className="flex flex-col gap-5" aria-labelledby="low-title">
              <h1 id="low-title" className="text-3xl font-medium">
                {t("lowTitle")}
              </h1>
              <p>{t("lowBody")}</p>
              <div className="flex flex-wrap gap-3">
                <Button size="lg" className="h-12 rounded-xl px-6" onClick={finish} disabled={submitting}>
                  {submitting ? t("submitting") : t("seeResult")}
                </Button>
                <Button size="lg" variant="outline" className="h-12 rounded-xl px-6" onClick={() => setState((s) => ({ ...s, wantsFull: true, idx: s.idx + 1 }))}>
                  {t("continueFull")}
                </Button>
              </div>
            </section>
          )}

          {screen.kind === "lifestyle" && (
            <section className="flex flex-col gap-6" aria-labelledby="life-title">
              <h1 id="life-title" className="text-3xl font-medium">
                {t("lifestyleTitle")}
              </h1>
              <p className="text-muted-foreground">{t("lifestyleLead")}</p>
              <label className="flex flex-col gap-2">
                <span className="font-medium">{t("sleep")}</span>
                <input type="number" inputMode="decimal" min={0} max={24} step={0.5} className={fieldClass} value={state.context.sleep_hours ?? ""} onChange={(e) => setState((s) => ({ ...s, context: { ...s.context, sleep_hours: e.target.value === "" ? undefined : Number(e.target.value) } }))} />
              </label>
              <label className="flex flex-col gap-2">
                <span className="font-medium">{t("duration")}</span>
                <select className={fieldClass} value={state.context.symptom_duration ?? ""} onChange={(e) => setState((s) => ({ ...s, context: { ...s.context, symptom_duration: e.target.value || undefined } }))}>
                  <option value="">—</option>
                  {DURATIONS.map((d) => (
                    <option key={d} value={d}>
                      {t(`durationOptions.${d}`)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-2">
                <span className="font-medium">{t("caffeine")}</span>
                <input type="number" inputMode="numeric" min={0} max={30} className={fieldClass} value={state.context.caffeine_cups ?? ""} onChange={(e) => setState((s) => ({ ...s, context: { ...s.context, caffeine_cups: e.target.value === "" ? undefined : Number(e.target.value) } }))} />
              </label>
              <fieldset className="flex flex-col gap-2">
                <legend className="mb-2 font-medium">{t("stress")}</legend>
                <div className="flex gap-3">
                  {[true, false].map((v) => (
                    <button key={String(v)} type="button" aria-pressed={state.context.stressful_event === v} onClick={() => setState((s) => ({ ...s, context: { ...s.context, stressful_event: v } }))} className={`min-h-12 flex-1 rounded-xl border ${state.context.stressful_event === v ? "border-sage-deep bg-accent font-medium" : "border-border bg-surface hover:bg-accent/60"}`}>
                      {v ? t("yes") : t("no")}
                    </button>
                  ))}
                </div>
              </fieldset>
              <div className="flex gap-3">
                <Button
                  size="lg"
                  className="h-12 rounded-xl px-7"
                  onClick={async () => {
                    const { sleep_hours, symptom_duration, caffeine_cups, stressful_event } = state.context;
                    await updateContext({ sleep_hours, symptom_duration, caffeine_cups, stressful_event });
                    go(1);
                  }}
                >
                  {tc("continue")}
                </Button>
                <Button size="lg" variant="ghost" className="h-12 rounded-xl" onClick={() => go(1)}>
                  {tc("skip")}
                </Button>
              </div>
            </section>
          )}

          {screen.kind === "freetext" && (
            <section className="flex flex-col gap-5" aria-labelledby="free-title">
              <h1 id="free-title" className="text-3xl font-medium">
                {t("freeTitle")}
              </h1>
              <p className="text-muted-foreground">{t("freeLead")}</p>
              <label className="flex flex-col gap-2">
                <span className="sr-only">{t("freeLabel")}</span>
                <textarea rows={5} maxLength={2000} className={`${fieldClass} py-3`} value={state.context.free_text ?? ""} onChange={(e) => setState((s) => ({ ...s, context: { ...s.context, free_text: e.target.value || undefined } }))} />
              </label>
              <Button size="lg" className="h-12 self-start rounded-xl px-7 text-base" onClick={finish} disabled={submitting}>
                {submitting ? t("submitting") : t("submit")}
              </Button>
            </section>
          )}
        </motion.div>
      </AnimatePresence>
    </main>
  );
}
