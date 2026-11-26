import { buildScreens, keyToOption, screenKey, sumAnswers, SCREENER_THRESHOLD } from "@/lib/flow";

describe("assessment flow", () => {
  it("starts with context and the two GAD-2 items", () => {
    expect(buildScreens(null, false).map(screenKey)).toEqual(["context", "gad2:0", "gad2:1"]);
  });

  it("stops at a short result when GAD-2 < 3", () => {
    const s = buildScreens(SCREENER_THRESHOLD - 1, false);
    expect(s.at(-1)).toEqual({ kind: "low" });
  });

  it("continues GAD-7 at item 3, then PHQ-9, OASIS, lifestyle and free text when GAD-2 >= 3", () => {
    const keys = buildScreens(3, false).map(screenKey);
    expect(keys.slice(3, 8)).toEqual(["gad7:2", "gad7:3", "gad7:4", "gad7:5", "gad7:6"]);
    expect(keys.filter((k) => k.startsWith("phq9"))).toHaveLength(9);
    expect(keys.filter((k) => k.startsWith("oasis"))).toHaveLength(5);
    expect(keys.slice(-2)).toEqual(["lifestyle", "freetext"]);
  });

  it("lets a low scorer opt into the full check", () => {
    expect(buildScreens(1, true).map(screenKey)).toContain("phq9:0");
  });

  it("sums only when every item is answered", () => {
    expect(sumAnswers({ a: 1 }, ["a", "b"])).toBeNull();
    expect(sumAnswers({ a: 1, b: 2 }, ["a", "b"])).toBe(3);
  });

  it("maps number keys to options", () => {
    expect(keyToOption("1", 4)).toBe(0);
    expect(keyToOption("4", 4)).toBe(3);
    expect(keyToOption("5", 4)).toBeNull();
    expect(keyToOption("a", 4)).toBeNull();
  });
});
