"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useAuth } from "@/lib/auth";

export function LanguageSwitcher() {
  const locale = useLocale();
  const router = useRouter();
  const t = useTranslations("common");
  const { user } = useAuth();
  const set = (l: string) => {
    document.cookie = `NEXT_LOCALE=${l}; path=/; max-age=31536000; samesite=lax`;
    if (user) import("@/lib/api").then(({ api }) => api.updateMe({ locale: l }).catch(() => undefined));
    router.refresh();
  };
  return (
    <div role="group" aria-label={t("language")} className="flex overflow-hidden rounded-lg border border-border text-sm">
      {[
        ["en", "English"],
        ["hi", "हिन्दी"],
      ].map(([code, label]) => (
        <button
          key={code}
          type="button"
          lang={code}
          aria-pressed={locale === code}
          onClick={() => set(code)}
          className={`min-h-9 px-3 ${locale === code ? "bg-primary text-primary-foreground" : "bg-surface hover:bg-accent"}`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

export function SiteHeader() {
  const t = useTranslations("common");
  const { user, logout } = useAuth();
  const router = useRouter();
  return (
    <header className="border-b border-border/70 bg-surface/80">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-4 focus:py-2">
        {t("skipToContent")}
      </a>
      <nav aria-label="Main" className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-5 gap-y-2 px-6 py-3">
        <Link href="/" className="mr-auto font-serif text-xl font-semibold text-sage-deep">
          {t("appName")}
        </Link>
        <Link href="/about" className="text-sm text-muted-foreground hover:text-foreground">
          {t("about")}
        </Link>
        {user ? (
          <>
            <Link href="/dashboard" className="text-sm text-muted-foreground hover:text-foreground">
              {t("dashboard")}
            </Link>
            {(user.role === "clinician" || user.role === "admin") && (
              <Link href="/clinician" className="text-sm text-muted-foreground hover:text-foreground">
                {t("clinician")}
              </Link>
            )}
            {user.role === "admin" && (
              <Link href="/admin" className="text-sm text-muted-foreground hover:text-foreground">
                {t("admin")}
              </Link>
            )}
            <button
              type="button"
              className="text-sm text-muted-foreground hover:text-foreground"
              onClick={async () => {
                await logout();
                router.push("/");
              }}
            >
              {t("signOut")}
            </button>
          </>
        ) : (
          <Link href="/login" className="text-sm text-muted-foreground hover:text-foreground">
            {t("signIn")}
          </Link>
        )}
        <LanguageSwitcher />
      </nav>
    </header>
  );
}
