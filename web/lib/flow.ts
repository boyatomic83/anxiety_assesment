/** Assessment flow (SPEC.md section 5). Pure functions so they are easy to test. */

export const SCREENER_THRESHOLD = 3; // GAD-2 >= 3 continues to the full check

export type Screen =
  | { kind: "context" }
  | { kind: "question"; qid: QuestionnaireId; index: number }
  | { kind: "low" }
  | { kind: "lifestyle" }
  | { kind: "freetext" };

export type QuestionnaireId = "gad2" | "gad7" | "phq9" | "oasis";
export const ITEM_COUNTS: Record<QuestionnaireId, number> = { gad2: 2, gad7: 7, phq9: 9, oasis: 5 };

const questions = (qid: QuestionnaireId, from = 0): Screen[] =>
  Array.from({ length: ITEM_COUNTS[qid] - from }, (_, i) => ({ kind: "question", qid, index: from + i }));

/**
 * Screens for the current state. `gad2Score` is null until both GAD-2 items are answered.
 * GAD-2 items are GAD-7 items 1-2, so the full check continues at GAD-7 item 3.
 */
export function buildScreens(gad2Score: number | null, wantsFull: boolean): Screen[] {
  const screens: Screen[] = [{ kind: "context" }, ...questions("gad2")];
  if (gad2Score === null) return screens;
  if (gad2Score < SCREENER_THRESHOLD && !wantsFull) return [...screens, { kind: "low" }];
  return [...screens, ...questions("gad7", 2), ...questions("phq9"), ...questions("oasis"), { kind: "lifestyle" }, { kind: "freetext" }];
}

export function sumAnswers(answers: Record<string, number>, ids: string[]): number | null {
  if (!ids.every((id) => id in answers)) return null;
  return ids.reduce((s, id) => s + answers[id], 0);
}

export const screenKey = (s: Screen) => (s.kind === "question" ? `${s.qid}:${s.index}` : s.kind);

/** Answers for one questionnaire. GAD-7 reuses the GAD-2 answers for its first two items. */
export function answersFor(qid: QuestionnaireId, itemIds: string[], answers: Record<string, number>) {
  return Object.fromEntries(itemIds.filter((id) => id in answers).map((id) => [id, answers[id]]));
}

/** Map a keyboard key ("1".."5") to an option index, or null. */
export function keyToOption(key: string, optionCount: number): number | null {
  const n = Number(key);
  return Number.isInteger(n) && n >= 1 && n <= optionCount ? n - 1 : null;
}
