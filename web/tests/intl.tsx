import { render } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import messages from "@/messages/en.json";

export function renderIntl(ui: React.ReactElement, locale = "en", msgs: Record<string, unknown> = messages) {
  return render(
    <NextIntlClientProvider locale={locale} messages={msgs} timeZone="Asia/Kolkata">
      {ui}
    </NextIntlClientProvider>,
  );
}
