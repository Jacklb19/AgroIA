"use client";

export default function KpiSpark({ data, color = "#1a7a4a" }) {
  const w = 64, h = 22, pad = 2;
  const min = Math.min(...data), max = Math.max(...data);
  const xs = data.map((_, i) => pad + (i * (w - pad * 2)) / (data.length - 1));
  const ys = data.map(
    (v) => pad + (1 - (v - min) / Math.max(0.0001, max - min)) * (h - pad * 2)
  );
  const d = xs.map((x, i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${ys[i].toFixed(1)}`).join(" ");
  return (
    <svg className="kpi-spark" viewBox={`0 0 ${w} ${h}`}>
      <path d={d} fill="none" stroke={color} strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={xs[xs.length - 1]} cy={ys[ys.length - 1]} r="2" fill={color} />
    </svg>
  );
}
