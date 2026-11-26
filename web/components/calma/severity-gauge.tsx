import { toneFor, toneHex } from "@/lib/bands";

type Band = { min: number; max: number; label: string; level: number };

const CX = 120;
const CY = 120;
const R = 96;

function point(fraction: number, r = R) {
  const angle = Math.PI * (1 - fraction); // left (0) -> right (1)
  return [CX + r * Math.cos(angle), CY - r * Math.sin(angle)];
}

function arc(from: number, to: number) {
  const [x1, y1] = point(from);
  const [x2, y2] = point(to);
  return `M ${x1} ${y1} A ${R} ${R} 0 0 1 ${x2} ${y2}`;
}

/** Semicircle severity gauge (SPEC.md section 9). */
export function SeverityGauge({ score, max, bands, label }: { score: number; max: number; bands: Band[]; label: string }) {
  const levels = bands.length;
  const frac = Math.min(Math.max(score / max, 0), 1);
  const [nx, ny] = point(frac, R - 26);
  return (
    <svg viewBox="0 0 240 140" role="img" aria-label={label} className="w-full max-w-xs">
      {bands.map((b) => (
        <path
          key={b.label}
          d={arc(b.min / (max + 1), (b.max + 1) / (max + 1))}
          stroke={toneHex[toneFor(b.level, levels)]}
          strokeWidth={22}
          fill="none"
          opacity={score >= b.min && score <= b.max ? 1 : 0.35}
        />
      ))}
      <line x1={CX} y1={CY} x2={nx} y2={ny} stroke="#1f2a2e" strokeWidth={4} strokeLinecap="round" />
      <circle cx={CX} cy={CY} r={7} fill="#1f2a2e" />
    </svg>
  );
}
