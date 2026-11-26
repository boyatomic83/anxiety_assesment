"use client";

import { use, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { ResultView, useDefs } from "@/components/calma/result-view";
import { api, type Result } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function ResultPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const t = useTranslations("results");
  const tc = useTranslations("common");
  const { ready } = useAuth();
  const [result, setResult] = useState<Result | null>(null);
  const [failed, setFailed] = useState(false);
  const defs = useDefs(result);

  useEffect(() => {
    if (!ready) return;
    api.result(id).then(setResult).catch(() => setFailed(true));
  }, [id, ready]);

  if (failed) return <main className="mx-auto max-w-[640px] px-6 py-16">{t("notFound")}</main>;
  if (!result) return <main className="mx-auto max-w-[640px] px-6 py-16">{tc("loading")}</main>;
  return <ResultView result={result} defs={defs} />;
}
