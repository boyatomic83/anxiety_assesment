import { useTranslations } from "next-intl";
import { Disclaimer } from "@/components/calma/disclaimer";

export default function AboutPage() {
  const t = useTranslations("about");
  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-16">
      <h1 className="text-4xl font-medium">{t("title")}</h1>
      <p>{t("p1")}</p>
      <p>{t("p2")}</p>
      <p>{t("p3")}</p>
      <h2 className="pt-4 text-2xl font-medium">{t("privacyTitle")}</h2>
      <p>{t("privacy")}</p>
      <Disclaimer />
    </main>
  );
}
