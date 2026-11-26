import type { Metadata } from "next";
import { Fraunces, Inter } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { getLocale } from "next-intl/server";
import { Providers } from "@/components/providers";
import { SiteHeader } from "@/components/calma/site-header";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"], display: "swap" });
const fraunces = Fraunces({ variable: "--font-fraunces", subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  title: "Calma — Anxiety screening",
  description:
    "A calm, private way to check in on anxiety using validated clinical questionnaires. A screening tool, not a diagnosis.",
};

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const locale = await getLocale();
  return (
    <html lang={locale}>
      <body className={`${inter.variable} ${fraunces.variable}`}>
        <NextIntlClientProvider>
          <Providers>
            <SiteHeader />
            <div id="main" tabIndex={-1} className="outline-none">
              {children}
            </div>
          </Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
