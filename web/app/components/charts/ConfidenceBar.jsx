"use client";

export default function ConfidenceBar({ low = 3.6, mid = 4.8, high = 6.0, vmin = 2.5, vmax = 7.0 }) {
  const w = 360, h = 64, pad = 14;
  const scale = (v) => pad + ((v - vmin) / (vmax - vmin)) * (w - pad * 2);
  const xLow = scale(low), xMid = scale(mid), xHigh = scale(high);
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} style={{ display: "block" }}>
      <defs>
        <linearGradient id="ciFill" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#22a35f" stopOpacity="0.18" />
          <stop offset="100%" stopColor="#22a35f" stopOpacity="0.32" />
        </linearGradient>
      </defs>
      <line x1={pad} x2={w - pad} y1={h / 2} y2={h / 2} stroke="#d1d5db" strokeWidth="1.5" />
      {[3, 4, 5, 6].map((v) => (
        <line key={v} x1={scale(v)} x2={scale(v)} y1={h / 2 - 4} y2={h / 2 + 4} stroke="#d1d5db" strokeWidth="1" />
      ))}
      <rect x={xLow} y={h / 2 - 9} width={xHigh - xLow} height="18" fill="url(#ciFill)" rx="4" stroke="#1a7a4a" strokeOpacity="0.4" />
      <line x1={xLow} x2={xLow} y1={h / 2 - 12} y2={h / 2 + 12} stroke="#1a7a4a" strokeWidth="2" />
      <line x1={xHigh} x2={xHigh} y1={h / 2 - 12} y2={h / 2 + 12} stroke="#1a7a4a" strokeWidth="2" />
      <circle cx={xMid} cy={h / 2} r="7" fill="#1a7a4a" stroke="white" strokeWidth="2.5" />
      <text x={xLow} y={h / 2 - 18} textAnchor="middle" fontSize="11" fill="#6b7280" fontFamily="ui-monospace, monospace">{low.toFixed(1)}</text>
      <text x={xMid} y={h / 2 + 28} textAnchor="middle" fontSize="12" fill="#0f3d24" fontWeight="700" fontFamily="ui-monospace, monospace">{mid.toFixed(1)}</text>
      <text x={xHigh} y={h / 2 - 18} textAnchor="middle" fontSize="11" fill="#6b7280" fontFamily="ui-monospace, monospace">{high.toFixed(1)}</text>
    </svg>
  );
}
