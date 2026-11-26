import en from "@/messages/en.json";
import hi from "@/messages/hi.json";

const keys = (o: object, p = ""): string[] =>
  Object.entries(o).flatMap(([k, v]) => (typeof v === "object" ? keys(v, `${p}${k}.`) : [`${p}${k}`]));

describe("i18n messages", () => {
  it("Hindi has exactly the English keys", () => {
    expect(keys(hi).sort()).toEqual(keys(en).sort());
  });

  it("every message keeps the same placeholders", () => {
    const get = (o: Record<string, unknown>, k: string) => k.split(".").reduce<unknown>((a, p) => (a as Record<string, unknown>)[p], o) as string;
    for (const k of keys(en)) {
      const ph = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort();
      expect(ph(get(hi, k))).toEqual(ph(get(en, k)));
    }
  });
});
