import Link from "next/link";
import { useTranslations } from "next-intl";
import { Card, CardContent } from "@/components/ui/card";
import { Disclaimer } from "@/components/calma/disclaimer";

export default function LandingPage() {
  const t = useTranslations("landing");
  const points = [1, 2, 3].map((n) => ({ title: t(`p${n}Title`), body: t(`p${n}Body`) }));
  return (
    <main className="mx-auto flex max-w-2xl flex-col justify-center gap-10 px-6 py-16">
      <header className="flex flex-col gap-5">
        <p className="text-sm font-medium tracking-wide text-slate-brand uppercase">Calma</p>
        <h1 className="text-4xl font-medium text-foreground sm:text-5xl">{t("title")}</h1>
        <p className="text-lg text-muted-foreground">{t("lead")}</p>
        <div className="flex flex-wrap items-center gap-4 pt-2">
          <Link
            href="/consent"
            className="inline-flex h-12 items-center rounded-xl bg-primary px-7 text-base font-medium text-primary-foreground hover:bg-primary/90 focus-visible:ring-[3px] focus-visible:ring-ring/50"
          >
            {t("start")}
          </Link>
          <span className="text-sm text-muted-foreground">{t("time")}</span>
        </div>
      </header>

      <ul className="grid gap-4 sm:grid-cols-3" aria-label={t("pointsLabel")}>
        {points.map((p) => (
          <li key={p.title}>
            <Card className="h-full rounded-2xl border-border/70 shadow-soft">
              <CardContent className="flex flex-col gap-2">
                <span aria-hidden className="h-1.5 w-8 rounded-full bg-sage" />
                <h2 className="text-lg font-medium">{p.title}</h2>
                <p className="text-sm text-muted-foreground">{p.body}</p>
              </CardContent>
            </Card>
          </li>
        ))}
      </ul>

      <Disclaimer />
    </main>
  );
}
