import { useTranslations } from "next-intl";
import type { TopFactor } from "@/lib/api";

/** "What drove this" bars. Positive impact raised the estimate, negative lowered it. */
export function ShapChart({ factors }: { factors: TopFactor[] }) {
  const t = useTranslations("results");
  const maxAbs = Math.max(...factors.map((f) => Math.abs(f.impact)), 1e-6);
  return (
    <ul className="flex flex-col gap-3" aria-label={t("factors")}>
      {factors.map((f) => {
        const pct = Math.round((Math.abs(f.impact) / maxAbs) * 100);
        const up = f.impact > 0;
        return (
          <li key={f.feature} className="grid grid-cols-[minmax(8rem,1fr)_2fr] items-center gap-3 text-sm">
            <span>{f.label}</span>
            <span className="flex items-center gap-2">
              <span className="h-3 flex-1 rounded-full bg-muted">
                <span aria-hidden className={`block h-3 rounded-full ${up ? "bg-band-moderate" : "bg-sage"}`} style={{ width: `${Math.max(pct, 4)}%` }} />
              </span>
              <span className="w-32 shrink-0 text-muted-foreground">{up ? t("raised") : t("lowered")}</span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}
