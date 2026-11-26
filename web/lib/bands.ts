/** Map a band level onto the four muted severity colours (SPEC.md section 9). */
export type Tone = "minimal" | "mild" | "moderate" | "severe";
const TONES: Tone[] = ["minimal", "mild", "moderate", "severe"];

export function toneFor(level: number | null | undefined, levelCount: number): Tone {
  if (level == null) return "minimal";
  if (levelCount <= 2) return level > 0 ? "moderate" : "minimal"; // screens: never "severe" red
  const idx = Math.round((level / Math.max(levelCount - 1, 1)) * 3);
  return TONES[Math.min(Math.max(idx, 0), 3)];
}

export const toneBg: Record<Tone, string> = {
  minimal: "bg-band-minimal",
  mild: "bg-band-mild",
  moderate: "bg-band-moderate",
  severe: "bg-band-severe",
};

export const toneHex: Record<Tone, string> = {
  minimal: "#7fb59a",
  mild: "#c9b458",
  moderate: "#d9905b",
  severe: "#b5615a",
};
