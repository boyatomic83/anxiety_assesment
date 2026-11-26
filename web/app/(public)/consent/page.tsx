"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { CONSENT_VERSION } from "@/lib/api";

export default function ConsentPage() {
  const t = useTranslations("consent");
  const router = useRouter();
  const [agreed, setAgreed] = useState(false);
  return (
    <main className="mx-auto flex max-w-xl flex-col gap-6 px-6 py-16">
      <h1 className="text-4xl font-medium">{t("title")}</h1>
      <p className="text-muted-foreground">{t("intro")}</p>
      <ul className="flex list-disc flex-col gap-3 pl-6">
        {(["c1", "c2", "c3", "c4"] as const).map((k) => (
          <li key={k}>{t(k)}</li>
        ))}
      </ul>
      <label className="flex min-h-12 cursor-pointer items-center gap-3 rounded-2xl border border-border bg-surface px-5 py-3">
        <input type="checkbox" className="size-5 accent-[var(--calma-sage-deep)]" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
        <span>{t("agree")}</span>
      </label>
      <Button
        size="lg"
        className="h-12 self-start rounded-xl px-7 text-base"
        disabled={!agreed}
        onClick={() => {
          sessionStorage.setItem("calma.consent", CONSENT_VERSION);
          router.push("/assess");
        }}
      >
        {t("start")}
      </Button>
      <p className="text-xs text-muted-foreground">{t("version", { version: CONSENT_VERSION })}</p>
    </main>
  );
}
