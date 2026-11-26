"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useFormatter, useLocale, useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { CrisisBanner } from "@/components/calma/crisis-screen";
import { Disclaimer } from "@/components/calma/disclaimer";
import { SeverityGauge } from "@/components/calma/severity-gauge";
import { ShapChart } from "@/components/calma/shap-chart";
import { api, downloadResponse, type Questionnaire, type Result } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { toneBg, toneFor } from "@/lib/bands";

function maxScore(q: Questionnaire): number {
  return q.items.reduce((s, i) => s + Math.max(...(i.options ?? q.options ?? []).map((o) => o.value)), 0);
}

type Def = Questionnaire & { bands: { min: number; max: number; label: string; level: number }[] };

export function ResultView({ result, defs, clinicianView = false }: { result: Result; defs: Record<string, Def>; clinicianView?: boolean }) {
  const t = useTranslations("results");
  const format = useFormatter();
  const { user } = useAuth();
  const [share, setShare] = useState<{ code: string; expires_at: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const primaryId = result.scores.gad7 ? "gad7" : result.scores.gad2 ? "gad2" : Object.keys(result.scores)[0];
  const primary = result.scores[primaryId];
  const primaryDef = defs[primaryId];
  const others = Object.entries(result.scores).filter(([id]) => id !== primaryId);

  return (
    <main className="mx-auto flex max-w-[720px] flex-col gap-8 px-6 py-10">
      <header className="flex flex-col gap-1">
        <h1 className="text-4xl font-medium">{t("title")}</h1>
        <p className="text-muted-foreground">{t("date", { date: format.dateTime(new Date(result.created_at), { dateStyle: "long" }) })}</p>
      </header>

      {result.flagged && result.crisis && <CrisisBanner helplines={result.crisis} />}

      {primary && primaryDef && (
        <Card className="rounded-2xl shadow-soft">
          <CardContent className="flex flex-col items-center gap-4 text-center sm:flex-row sm:text-left">
            <SeverityGauge
              score={primary.total}
              max={maxScore(primaryDef)}
              bands={primaryDef.bands}
              label={t("gaugeLabel", { name: primaryDef.name, score: primary.total, max: maxScore(primaryDef), band: primary.band ?? "" })}
            />
            <div className="flex flex-col gap-2">
              <p className="text-sm font-medium text-slate-brand uppercase">
                {t("validated")} · {primaryDef.name}
              </p>
              <p className="font-serif text-3xl">
                {primary.band} <span className="text-lg text-muted-foreground">({t("scoreOf", { score: primary.total, max: maxScore(primaryDef) })})</span>
              </p>
              {(primaryId === "gad7" || primaryId === "gad2") && primary.level != null && <p>{t(`summary.${primaryId}.${primary.level}`)}</p>}
            </div>
          </CardContent>
        </Card>
      )}

      {others.length > 0 && (
        <section aria-labelledby="others" className="flex flex-col gap-3">
          <h2 id="others" className="text-2xl font-medium">
            {t("others")}
          </h2>
          <ul className="grid gap-3 sm:grid-cols-2">
            {others.map(([id, s]) => {
              const def = defs[id];
              const levels = def?.bands.length ?? 4;
              return (
                <li key={id} className="rounded-2xl border border-border bg-surface p-4 shadow-soft">
                  <p className="font-medium">{def?.name ?? id}</p>
                  {s.band ? (
                    <p className="mt-1 flex items-center gap-2">
                      <span aria-hidden className={`size-3 rounded-full ${toneBg[toneFor(s.level, levels)]}`} />
                      {s.band} · {def ? t("scoreOf", { score: s.total, max: maxScore(def) }) : s.total}
                    </p>
                  ) : (
                    <ul className="mt-1 text-sm">
                      {Object.entries(s.subscales).map(([k, sub]) => (
                        <li key={k} className="flex items-center gap-2">
                          <span aria-hidden className={`size-3 rounded-full ${toneBg[toneFor(sub.level, 5)]}`} />
                          {k}: {sub.band} ({sub.score})
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      )}

      <section aria-labelledby="ai" className="flex flex-col gap-3 rounded-2xl border border-dashed border-border p-5">
        <h2 id="ai" className="text-xl font-medium">
          {t("aiTitle")}
        </h2>
        <p className="text-sm text-muted-foreground">{t("aiBody")}</p>
        {result.ml ? (
          <>
            <p className="font-medium">
              {t("aiComposite", { label: t(`composite.${result.ml.composite_label}`) })} ·{" "}
              <span className="text-muted-foreground">{t("aiConfidence", { value: format.number(result.ml.confidence, { style: "percent" }) })}</span>
            </p>
            {result.ml.agrees_with_validated !== null && <p className="text-sm">{result.ml.agrees_with_validated ? t("aiAgree") : t("aiDisagree")}</p>}
            {result.ml.top_factors.length > 0 && (
              <>
                <h3 className="pt-2 font-medium">{t("factors")}</h3>
                <ShapChart factors={result.ml.top_factors} />
              </>
            )}
            {result.ml.model_version.includes("synth") && <p className="text-xs text-muted-foreground">{t("aiSynthetic")}</p>}
          </>
        ) : (
          <p className="text-sm">{t("aiNone")}</p>
        )}
        {result.response_quality && !result.response_quality.ok && (
          <p className="rounded-xl bg-band-mild/15 px-4 py-3 text-sm">
            {t("quality", { flags: result.response_quality.flags.map((f) => t(`qualityFlags.${f}`)).join(", ") })}
          </p>
        )}
      </section>

      {!clinicianView && (
        <>
          <section aria-labelledby="next" className="flex flex-col gap-3">
            <h2 id="next" className="text-2xl font-medium">
              {t("next")}
            </h2>
            <ul className="flex list-disc flex-col gap-2 pl-6">
              <li>{t("n1")}</li>
              <li>{t("n2")}</li>
              <li>{t("n3")}</li>
            </ul>
          </section>

          <div className="flex flex-wrap gap-3">
            <Button
              size="lg"
              className="h-12 rounded-xl px-6"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await downloadResponse(await api.resultPdf(result.id), "calma-report.pdf");
                } finally {
                  setBusy(false);
                }
              }}
            >
              {t("pdf")}
            </Button>
            {user ? (
              <Button size="lg" variant="outline" className="h-12 rounded-xl px-6" onClick={async () => setShare(await api.share(result.id))}>
                {t("share")}
              </Button>
            ) : (
              <Link href="/register" className="inline-flex h-12 items-center rounded-xl border border-border bg-surface px-6 font-medium hover:bg-accent">
                {t("save")}
              </Link>
            )}
            <Link href="/consent" className="inline-flex h-12 items-center rounded-xl px-4 text-sage-deep underline-offset-4 hover:underline">
              {t("newCheck")}
            </Link>
          </div>
          {!user && <p className="text-sm text-muted-foreground">{t("saveBody")}</p>}
          {share && (
            <p role="status" className="rounded-xl bg-accent px-4 py-3">
              {t("shareCode", { code: share.code, date: format.dateTime(new Date(share.expires_at), { dateStyle: "medium" }) })}
            </p>
          )}
        </>
      )}

      <Disclaimer long />
    </main>
  );
}

export function useDefs(result: Result | null) {
  const locale = useLocale();
  const [defs, setDefs] = useState<Record<string, Def>>({});
  useEffect(() => {
    if (!result) return;
    Promise.all(Object.keys(result.scores).map((id) => api.questionnaire(id, locale) as Promise<Def>)).then((list) =>
      setDefs(Object.fromEntries(list.map((d) => [d.id, d]))),
    );
  }, [result, locale]);
  return defs;
}

