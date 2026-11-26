"use client";

import { useEffect, useId, useRef } from "react";
import { keyToOption } from "@/lib/flow";
import type { Option } from "@/lib/api";

type Props = {
  timeframe?: string;
  text: string;
  options: Option[];
  value: number | undefined;
  onAnswer: (value: number) => void;
  progressLabel: string;
  keysHint?: string;
};

/** One validated item per screen. Texts come from the API, never from this code. */
export function QuestionCard({ timeframe, text, options, value, onAnswer, progressLabel, keysHint }: Props) {
  const id = useId();
  const groupRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.altKey || e.ctrlKey || e.metaKey) return;
      const target = e.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      const idx = keyToOption(e.key, options.length);
      if (idx !== null) {
        e.preventDefault();
        onAnswer(options[idx].value);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [options, onAnswer]);

  useEffect(() => {
    // Move focus to the new question for screen-reader and keyboard users.
    groupRef.current?.focus();
  }, [text]);

  const onArrow = (e: React.KeyboardEvent, i: number) => {
    const dir = e.key === "ArrowDown" || e.key === "ArrowRight" ? 1 : e.key === "ArrowUp" || e.key === "ArrowLeft" ? -1 : 0;
    if (!dir) return;
    e.preventDefault();
    const next = (i + dir + options.length) % options.length;
    (groupRef.current?.querySelectorAll<HTMLButtonElement>("[role=radio]")[next])?.focus();
  };

  return (
    <section aria-labelledby={`${id}-q`} className="flex flex-col gap-5">
      <p className="text-sm font-medium text-slate-brand">{progressLabel}</p>
      {timeframe && <p className="text-muted-foreground">{timeframe}</p>}
      <h2 id={`${id}-q`} className="text-2xl font-medium sm:text-3xl">
        {text}
      </h2>
      <div ref={groupRef} tabIndex={-1} role="radiogroup" aria-labelledby={`${id}-q`} className="flex flex-col gap-3 outline-none">
        {options.map((o, i) => {
          const selected = value === o.value;
          return (
            <button
              key={o.value}
              type="button"
              role="radio"
              aria-checked={selected}
              tabIndex={selected || (value === undefined && i === 0) ? 0 : -1}
              onClick={() => onAnswer(o.value)}
              onKeyDown={(e) => onArrow(e, i)}
              className={`flex min-h-14 w-full items-center gap-4 rounded-2xl border px-5 py-3 text-left text-base transition-colors duration-150 focus-visible:ring-[3px] focus-visible:ring-ring/50 ${
                selected ? "border-sage-deep bg-accent font-medium" : "border-border bg-surface hover:border-sage hover:bg-accent/60"
              }`}
            >
              <kbd aria-hidden className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-muted font-sans text-sm text-muted-foreground">
                {i + 1}
              </kbd>
              <span>{o.label}</span>
            </button>
          );
        })}
      </div>
      {keysHint && <p className="hidden text-sm text-muted-foreground sm:block">{keysHint}</p>}
    </section>
  );
}
