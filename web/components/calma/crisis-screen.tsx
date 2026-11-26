"use client";

import { useEffect, useRef } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import type { Helplines } from "@/lib/api";

/** Full-screen, calm crisis support (SPEC.md section 5). Never blocks the results. */
export function CrisisScreen({ helplines, onContinue }: { helplines: Helplines; onContinue: () => void }) {
  const t = useTranslations("crisis");
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => headingRef.current?.focus(), []);
  return (
    <div role="alertdialog" aria-modal="true" aria-labelledby="crisis-title" aria-describedby="crisis-body" className="fixed inset-0 z-50 overflow-y-auto bg-background">
      <div className="mx-auto flex min-h-full max-w-xl flex-col justify-center gap-6 px-6 py-12">
        <h1 id="crisis-title" ref={headingRef} tabIndex={-1} className="text-3xl font-medium outline-none sm:text-4xl">
          {t("title")}
        </h1>
        <p id="crisis-body" className="text-lg text-muted-foreground">
          {t("body")}
        </p>
        <HelplineList helplines={helplines} />
        <Button variant="outline" size="lg" className="h-12 self-start rounded-xl px-6" onClick={onContinue}>
          {t("continue")}
        </Button>
      </div>
    </div>
  );
}

export function HelplineList({ helplines }: { helplines: Helplines }) {
  const t = useTranslations("crisis");
  return (
    <ul className="flex flex-col gap-3">
      {helplines.helplines.map((h) => (
        <li key={h.name} className="rounded-2xl border border-border bg-surface p-5 shadow-soft">
          <p className="font-medium">{h.name}</p>
          {h.number ? (
            <p className="mt-1">
              <a href={`tel:${h.number.replace(/[^\d+]/g, "")}`} className="text-2xl font-semibold text-sage-deep underline-offset-4 hover:underline">
                {t("call", { number: h.number })}
              </a>
              {h.alt_number && <span className="ml-2 text-muted-foreground">({t("also", { number: h.alt_number })})</span>}
            </p>
          ) : h.url ? (
            <a href={h.url} className="mt-1 inline-block text-sage-deep underline" target="_blank" rel="noreferrer">
              {h.url.replace(/^https?:\/\//, "")}
            </a>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

export function CrisisBanner({ helplines }: { helplines: Helplines }) {
  const t = useTranslations("crisis");
  return (
    <section aria-labelledby="crisis-banner" className="rounded-2xl border border-band-severe/40 bg-surface p-5">
      <h2 id="crisis-banner" className="mb-3 text-lg font-medium">
        {t("title")} {t("banner")}
      </h2>
      <HelplineList helplines={helplines} />
    </section>
  );
}
