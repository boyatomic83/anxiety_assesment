import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

const points = [
  { title: "Validated questionnaires", body: "GAD-7, PHQ-9 and OASIS, scored with their official rules." },
  { title: "Private by design", body: "Your answers are encrypted. Guests leave no trace after 24 hours." },
  { title: "About 5 minutes", body: "One question at a time, at your own pace. You can stop whenever you like." },
];

export default function LandingPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-10 px-6 py-16">
      <header className="flex flex-col gap-5">
        <p className="text-sm font-medium tracking-wide text-slate-brand uppercase">Calma</p>
        <h1 className="text-4xl font-medium text-foreground sm:text-5xl">
          A quiet moment to check in with yourself.
        </h1>
        <p className="text-lg text-muted-foreground">
          Answer a few short, clinically validated questions about how you&apos;ve been feeling over the
          last two weeks, and get a clear, plain-language summary.
        </p>
        <div className="flex flex-wrap items-center gap-4 pt-2">
          {/* The assessment flow arrives in Phase 3. */}
          <Button size="lg" className="h-12 rounded-xl px-7 text-base" disabled aria-describedby="coming-soon">
            Start a check-in
          </Button>
          <span id="coming-soon" className="text-sm text-muted-foreground">
            Coming soon
          </span>
        </div>
      </header>

      <ul className="grid gap-4 sm:grid-cols-3" aria-label="What to expect">
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

      <footer className="rounded-2xl bg-muted px-5 py-4 text-sm text-muted-foreground">
        <strong className="font-semibold text-foreground">Calma is a screening tool, not a diagnosis.</strong>{" "}
        If you are in crisis or thinking about harming yourself, please call Tele-MANAS on 14416 or
        emergency services on 112.
      </footer>
    </main>
  );
}
