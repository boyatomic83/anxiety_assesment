"use client";

import { useEffect, useState } from "react";
import { useFormatter, useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { api, type AuditEntry, type User } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function AdminPage() {
  const t = useTranslations("admin");
  const format = useFormatter();
  const { user, ready } = useAuth();
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [model, setModel] = useState<Record<string, unknown> | null>(null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<User["role"]>("clinician");
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    if (ready && user?.role === "admin") {
      api.audit().then(setAudit);
      api.models().then((m) => setModel(m.active));
    }
  }, [ready, user]);

  if (!ready) return null;
  if (user?.role !== "admin") return <main className="mx-auto max-w-[640px] px-6 py-16">{t("notAllowed")}</main>;

  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-8 px-6 py-10">
      <h1 className="text-4xl font-medium">{t("title")}</h1>
      <section aria-labelledby="model" className="flex flex-col gap-2">
        <h2 id="model" className="text-2xl font-medium">{t("model")}</h2>
        <pre className="overflow-x-auto rounded-2xl bg-muted p-4 text-xs">
          {JSON.stringify(model && { model_version: model.model_version, model_type: model.model_type, trained_on: model.trained_on, cv_metrics: model.cv_metrics }, null, 2)}
        </pre>
      </section>
      <section aria-labelledby="role" className="flex flex-col gap-3">
        <h2 id="role" className="text-2xl font-medium">{t("role")}</h2>
        <form
          className="flex flex-wrap gap-3"
          onSubmit={async (e) => {
            e.preventDefault();
            try {
              const u = await api.setRole(email, role);
              setStatus(`${u.email}: ${u.role}`);
              setAudit(await api.audit());
            } catch (err) {
              setStatus(err instanceof Error ? err.message : "error");
            }
          }}
        >
          <input type="email" required aria-label="Email" placeholder="email@example.com" value={email} onChange={(e) => setEmail(e.target.value)} className="min-h-11 flex-1 rounded-xl border border-input bg-surface px-4" />
          <select aria-label="Role" value={role} onChange={(e) => setRole(e.target.value as User["role"])} className="min-h-11 rounded-xl border border-input bg-surface px-3">
            <option value="user">user</option>
            <option value="clinician">clinician</option>
            <option value="admin">admin</option>
          </select>
          <Button type="submit" className="h-11 rounded-xl">{t("save")}</Button>
        </form>
        {status && <p role="status" className="text-sm">{status}</p>}
      </section>
      <section aria-labelledby="audit" className="flex flex-col gap-3">
        <h2 id="audit" className="text-2xl font-medium">{t("audit")}</h2>
        <div className="overflow-x-auto rounded-2xl border border-border bg-surface">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted text-muted-foreground">
              <tr>
                <th scope="col" className="px-4 py-2">Time</th>
                <th scope="col" className="px-4 py-2">Actor</th>
                <th scope="col" className="px-4 py-2">Action</th>
                <th scope="col" className="px-4 py-2">Target</th>
              </tr>
            </thead>
            <tbody>
              {audit.map((a) => (
                <tr key={a.id} className="border-t border-border">
                  <td className="px-4 py-2">{format.dateTime(new Date(a.created_at), { dateStyle: "short", timeStyle: "short" })}</td>
                  <td className="px-4 py-2 font-mono">{a.actor_id?.slice(0, 8) ?? "—"}</td>
                  <td className="px-4 py-2">{a.action}</td>
                  <td className="px-4 py-2 font-mono">{a.target ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
