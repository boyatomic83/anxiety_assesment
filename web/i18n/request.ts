import { getRequestConfig } from "next-intl/server";
import { cookies } from "next/headers";

export const LOCALES = ["en", "hi"] as const;
export type Locale = (typeof LOCALES)[number];
export const LOCALE_COOKIE = "NEXT_LOCALE";

export default getRequestConfig(async () => {
  const store = await cookies();
  const locale: Locale = store.get(LOCALE_COOKIE)?.value === "hi" ? "hi" : "en";
  return { locale, messages: (await import(`../messages/${locale}.json`)).default };
});
