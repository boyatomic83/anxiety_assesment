"use client";

import { useCallback, useEffect, useState } from "react";
import { useFormatter, useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { ResultView, useDefs } from "@/components/calma/result-view";
import { api, downloadResponse, type PatientResult, type Result } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function ClinicianPage() {
  const t = useTranslations("clinician");
  const tc = useTranslations("common");
  const format = useFormatter();
  const { user, ready } = useAuth();
  const [rows, setRows] = useState<PatientResult[]>([]);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<Result | null>(null);
  const defs = useDefs(open);
  const allowed = user && (user.role === "clinician" || user.role === "admin");

  const load = useCallback(() => api.patients().then(setRows), []);
  useEffect(() => {
    if (ready && allowed) void load();
  }, [ready, allowed, load]);

  if (!ready) return null;
  if (!allowed) return <main className="mx-auto max-w-[640px] px-6 py-16">{t("notAllowed")}</main>;
  if (open)
    return (
      <div>
        <div className="mx-auto max-w-[720px] px-6 pt-6">
          <button type="button" className="min-h-10 text-sm text-muted-foreground hover:text-foreground" onClick={() => setOpen(null)}>
            ← {tc("back")}
          </button>
        </div>
        <ResultView result={open} defs={defs} clinicianView />
      </div>
    );

  const flagged = rows.filter((r) => r.flagged);
  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-8 px-6 py-10">
      <h1 className="text-4xl font-medium">{t("title")}</h1>
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={async (e) => {
          e.preventDefault();
          setError(null);
          try {
            await api.redeem(code);
            setCode("");
            await load();
          } catch (err) {
            setError(err instanceof Error ? err.message : tc("error"));
          }
        }}
      >
        <label className="flex flex-col gap-2">
          <span className="font-medium">{t("redeem")}</span>
          <input
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            placeholder={t("code")}
            aria-label={t("code")}
            className="min-h-12 rounded-xl border border-input bg-surface px-4 font-mono tracking-widest uppercase outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
          />
        </label>
        <Button type="submit" className="h-12 rounded-xl px-6" disabled={code.length < 6}>
          {t("add")}
        </Button>
        <Button type="button" variant="outline" className="ml-auto h-12 rounded-xl" onClick={async () => downloadResponse(await api.clinicianCsv(), "calma-shared-results.csv")}>
          {t("export")}
        </Button>
      </form>
      {error && (
        <p role="alert" className="rounded-xl bg-band-severe/10 px-4 py-3 text-sm">
          {error}
        </p>
      )}

      {[
        { title: t("flagged"), list: flagged },
        { title: t("patients"), list: rows },
      ].map(({ title, list }) => (
        <section key={title} aria-label={title} className="flex flex-col gap-3">
          <h2 className="text-2xl font-medium">
            {title} ({list.length})
          </h2>
          {list.length === 0 ? (
            <p className="text-muted-foreground">{t("none")}</p>
          ) : (
            <div className="overflow-x-auto rounded-2xl border border-border bg-surface">
              <table className="w-full text-left text-sm">
                <thead className="bg-muted text-muted-foreground">
                  <tr>
                    <th scope="col" className="px-4 py-2">{t("patient")}</th>
                    <th scope="col" className="px-4 py-2">{t("date")}</th>
                    <th scope="col" className="px-4 py-2">{t("scores")}</th>
                    <th scope="col" className="px-4 py-2">{t("ai")}</th>
                    <th scope="col" className="px-4 py-2"><span className="sr-only">Open</span></th>
                  </tr>
                </thead>
                <tbody>
                  {list.map((r) => (
                    <tr key={r.result_id} className="border-t border-border">
                      <td className="px-4 py-2 font-mono">
                        {r.flagged && <span aria-label={t("flagged")} className="mr-2 inline-block size-2.5 rounded-full bg-band-severe" />}
                        {r.patient_ref}
                      </td>
                      <td className="px-4 py-2">{format.dateTime(new Date(r.created_at), { dateStyle: "medium" })}</td>
                      <td className="px-4 py-2">
                        {Object.entries(r.scores)
                          .map(([id, s]) => `${id.toUpperCase()} ${s.total}${s.band ? ` ${s.band}` : ""}`)
                          .join(" · ")}
                      </td>
                      <td className="px-4 py-2">{r.ml_composite ?? "—"}</td>
                      <td className="px-4 py-2">
                        <button type="button" className="min-h-10 text-sage-deep underline-offset-4 hover:underline" onClick={async () => setOpen(await api.clinicianResult(r.result_id))}>
                          →
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      ))}
    </main>
  );
}
