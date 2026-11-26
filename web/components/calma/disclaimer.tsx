import { useTranslations } from "next-intl";

export function Disclaimer({ long = false }: { long?: boolean }) {
  const t = useTranslations("common");
  return (
    <p role="note" className="rounded-2xl bg-muted px-5 py-4 text-sm text-muted-foreground">
      {long ? (
        <strong className="font-semibold text-foreground">{t("disclaimerLong")}</strong>
      ) : (
        <>
          <strong className="font-semibold text-foreground">{t("disclaimer")}</strong> {t("crisisLine")}
        </>
      )}
    </p>
  );
}
