"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useFormatter, useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { TrendChart } from "@/components/calma/trend-chart";
import { api, type HistoryItem } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function DashboardPage() {
  const t = useTranslations("dashboard");
  const format = useFormatter();
  const router = useRouter();
  const { user, ready, setUser } = useAuth();
  const [history, setHistory] = useState<HistoryItem[] | null>(null);
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    if (ready && user) api.history().then(setHistory);
  }, [ready, user]);

  if (!ready) return null;
  if (!user)
    return (
      <main className="mx-auto max-w-[640px] px-6 py-16">
        <p>{t("signInNeeded")}</p>
        <Link href="/login" className="text-sage-deep underline">
          →
        </Link>
      </main>
    );

  const trend = (history ?? [])
    .filter((h) => h.scores.gad7 || h.scores.phq9)
    .map((h) => ({ date: format.dateTime(new Date(h.created_at), { day: "numeric", month: "short" }), gad7: h.scores.gad7?.total, phq9: h.scores.phq9?.total }));

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-10 px-6 py-10">
      <h1 className="text-4xl font-medium">{t("title")}</h1>

      <section aria-labelledby="trend" className="flex flex-col gap-3">
        <h2 id="trend" className="text-2xl font-medium">
          {t("trend")}
        </h2>
        {trend.length > 0 ? <TrendChart data={trend} label={t("trendLabel")} /> : <p className="text-muted-foreground">{t("empty")}</p>}
      </section>

      {history && history.length > 0 && (
        <section aria-labelledby="hist" className="flex flex-col gap-3">
          <h2 id="hist" className="text-2xl font-medium">
            {t("history")}
          </h2>
          <ul className="flex flex-col divide-y divide-border rounded-2xl border border-border bg-surface">
            {[...history].reverse().map((h) => (
              <li key={h.result_id} className="flex flex-wrap items-center gap-3 px-5 py-3">
                <span className="w-32">{format.dateTime(new Date(h.created_at), { dateStyle: "medium" })}</span>
                <span className="flex-1 text-sm text-muted-foreground">
                  {Object.entries(h.scores)
                    .map(([id, s]) => `${id.toUpperCase()} ${s.total}${s.band ? ` (${s.band})` : ""}`)
                    .join(" · ")}
                </span>
                {h.flagged && <span className="rounded-full bg-band-severe/15 px-2 py-0.5 text-xs">{t("flagged")}</span>}
                <Link href={`/results/${h.result_id}`} className="text-sage-deep underline-offset-4 hover:underline">
                  {t("view")}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="rem" className="flex flex-col gap-3">
        <h2 id="rem" className="text-2xl font-medium">
          {t("reminders")}
        </h2>
        <p className="text-muted-foreground">{t("remindersLead")}</p>
        <div role="group" aria-labelledby="rem" className="flex flex-wrap gap-2">
          {[null, 7, 14, 30, 90].map((d) => (
            <button
              key={String(d)}
              type="button"
              aria-pressed={user.reminder_days === d}
              onClick={async () => setUser(await api.updateMe(d ? { reminder_days: d } : { clear_reminder: true }))}
              className={`min-h-11 rounded-xl border px-4 ${user.reminder_days === d ? "border-sage-deep bg-accent font-medium" : "border-border bg-surface hover:bg-accent/60"}`}
            >
              {d ? t("every", { days: d }) : t("off")}
            </button>
          ))}
        </div>
      </section>

      <section aria-labelledby="data" className="flex flex-col gap-3">
        <h2 id="data" className="text-2xl font-medium">
          {t("privacy")}
        </h2>
        <div className="flex flex-wrap gap-3">
          <Button
            variant="outline"
            className="h-11 rounded-xl"
            onClick={async () => {
              const data = await api.exportData();
              const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
              const a = document.createElement("a");
              a.href = URL.createObjectURL(blob);
              a.download = "calma-my-data.json";
              a.click();
              URL.revokeObjectURL(a.href);
            }}
          >
            {t("export")}
          </Button>
          {!confirming && (
            <Button variant="outline" className="h-11 rounded-xl border-band-severe/50" onClick={() => setConfirming(true)}>
              {t("delete")}
            </Button>
          )}
        </div>
        {confirming && (
          <div role="alertdialog" aria-labelledby="del-q" className="flex flex-col gap-3 rounded-2xl border border-band-severe/50 bg-surface p-5">
            <p id="del-q">{t("deleteConfirm")}</p>
            <div className="flex gap-3">
              <Button
                className="h-11 rounded-xl bg-band-severe text-white hover:bg-band-severe/90"
                onClick={async () => {
                  await api.deleteMe();
                  setUser(null);
                  router.push("/");
                }}
              >
                {t("deleteYes")}
              </Button>
              <Button variant="ghost" className="h-11 rounded-xl" onClick={() => setConfirming(false)}>
                {t("cancel")}
              </Button>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
