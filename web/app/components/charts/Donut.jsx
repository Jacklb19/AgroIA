"use client";

export default function Donut({ size = 200, segments }) {
  const total = segments.reduce((s, x) => s + x.value, 0);
  const r = size / 2 - 18;
  const c = size / 2;
  const stroke = 22;
  const circumference = 2 * Math.PI * r;
  let acc = 0;
  return (
    <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size}>
      <circle cx={c} cy={c} r={r} fill="none" stroke="#f3f4f6" strokeWidth={stroke} />
      {segments.map((seg, i) => {
        const segLen = (seg.value / total) * circumference;
        const offset = -((acc / total) * circumference);
        acc += seg.value;
        return (
          <circle
            key={i}
            cx={c} cy={c} r={r}
            fill="none"
            stroke={seg.color}
            strokeWidth={stroke}
            strokeDasharray={`${segLen} ${circumference}`}
            strokeDashoffset={offset}
            transform={`rotate(-90 ${c} ${c})`}
            strokeLinecap="butt"
          />
        );
      })}
      <text x={c} y={c - 4} textAnchor="middle" fontFamily='"Inter Tight", system-ui' fontSize="26" fontWeight="700" fill="#111827" letterSpacing="-0.03em">{total}</text>
      <text x={c} y={c + 16} textAnchor="middle" fontSize="10.5" fill="#6b7280" letterSpacing="0.1em" fontFamily="ui-monospace, monospace">ALERTAS</text>
    </svg>
  );
}
