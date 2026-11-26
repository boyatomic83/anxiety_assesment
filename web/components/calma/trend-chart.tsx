"use client";

import { CartesianGrid, Legend, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { toneHex } from "@/lib/bands";

export type TrendPoint = { date: string; gad7?: number; phq9?: number };

// GAD-7 severity ranges (Spitzer et al., 2006) shaded behind the lines.
const GAD7_BANDS = [
  { y1: 0, y2: 4, fill: toneHex.minimal },
  { y1: 5, y2: 9, fill: toneHex.mild },
  { y1: 10, y2: 14, fill: toneHex.moderate },
  { y1: 15, y2: 21, fill: toneHex.severe },
];

export function TrendChart({ data, label }: { data: TrendPoint[]; label: string }) {
  return (
    <figure aria-label={label} className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: -16 }}>
          {GAD7_BANDS.map((b) => (
            <ReferenceArea key={b.y1} y1={b.y1} y2={b.y2 + 0.99} fill={b.fill} fillOpacity={0.14} ifOverflow="hidden" />
          ))}
          <CartesianGrid stroke="#e2e6e2" vertical={false} />
          <XAxis dataKey="date" tick={{ fontSize: 12 }} />
          <YAxis domain={[0, 27]} ticks={[0, 5, 10, 15, 20, 27]} tick={{ fontSize: 12 }} />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="gad7" name="GAD-7" stroke="#4a7561" strokeWidth={2.5} dot={{ r: 4 }} connectNulls />
          <Line type="monotone" dataKey="phq9" name="PHQ-9" stroke="#5a7184" strokeWidth={2.5} strokeDasharray="5 4" dot={{ r: 4 }} connectNulls />
        </LineChart>
      </ResponsiveContainer>
      <figcaption className="sr-only">
        {data.map((d) => `${d.date}: GAD-7 ${d.gad7 ?? "-"}, PHQ-9 ${d.phq9 ?? "-"}`).join("; ")}
      </figcaption>
    </figure>
  );
}
