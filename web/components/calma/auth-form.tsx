"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";

const field = "min-h-12 w-full rounded-xl border border-input bg-surface px-4 text-base outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const t = useTranslations("auth");
  const locale = useLocale();
  const router = useRouter();
  const { login, register } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  return (
    <main className="mx-auto flex max-w-md flex-col gap-6 px-6 py-16">
      <h1 className="text-4xl font-medium">{mode === "login" ? t("loginTitle") : t("registerTitle")}</h1>
      {mode === "register" && <p className="text-muted-foreground">{t("registerLead")}</p>}
      <form
        className="flex flex-col gap-4"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError(null);
          try {
            const user = mode === "login" ? await login(email, password) : await register(email, password, locale);
            router.push(user.role === "clinician" ? "/clinician" : "/dashboard");
          } catch (err) {
            setError(t("failed", { message: err instanceof Error ? err.message : "" }));
          } finally {
            setBusy(false);
          }
        }}
      >
        <label className="flex flex-col gap-2">
          <span className="font-medium">{t("email")}</span>
          <input className={field} type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="flex flex-col gap-2">
          <span className="font-medium">{t("password")}</span>
          <input
            className={field}
            type="password"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            minLength={mode === "register" ? 10 : undefined}
            required
            aria-describedby={mode === "register" ? "pw-hint" : undefined}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {mode === "register" && (
            <span id="pw-hint" className="text-sm text-muted-foreground">
              {t("passwordHint")}
            </span>
          )}
        </label>
        {error && (
          <p role="alert" className="rounded-xl bg-band-severe/10 px-4 py-3 text-sm">
            {error}
          </p>
        )}
        <Button type="submit" size="lg" className="h-12 rounded-xl text-base" disabled={busy}>
          {mode === "login" ? t("login") : t("register")}
        </Button>
      </form>
      <Link href={mode === "login" ? "/register" : "/login"} className="text-sage-deep underline-offset-4 hover:underline">
        {mode === "login" ? t("noAccount") : t("haveAccount")}
      </Link>
    </main>
  );
}
