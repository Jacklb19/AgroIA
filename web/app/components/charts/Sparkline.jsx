"use client";

export default function Sparkline({ height = 200 }) {
  const pts = [3.4, 3.5, 3.7, 3.6, 3.9, 4.1, 4.2, 4.0, 4.3, 4.6, 4.8];
  const w = 460, h = height, pad = { l: 32, r: 28, t: 22, b: 32 };
  const xs = pts.map((_, i) => pad.l + (i * (w - pad.l - pad.r)) / (pts.length - 1));
  const minY = 3.2, maxY = 5.0;
  const ys = pts.map((v) => pad.t + (1 - (v - minY) / (maxY - minY)) * (h - pad.t - pad.b));
  const linePath = xs.map((x, i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${ys[i].toFixed(1)}`).join(" ");
  const areaPath = `${linePath} L ${xs[xs.length - 1]} ${h - pad.b} L ${xs[0]} ${h - pad.b} Z`;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} style={{ display: "block" }}>
      <defs>
        <linearGradient id="spkArea" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#22a35f" stopOpacity="0.36" />
          <stop offset="100%" stopColor="#22a35f" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[0, 1, 2, 3].map((i) => {
        const y = pad.t + (i * (h - pad.t - pad.b)) / 3;
        return <line key={i} x1={pad.l} x2={w - pad.r} y1={y} y2={y} stroke="#e5e7eb" strokeWidth="1" />;
      })}
      <path d={areaPath} fill="url(#spkArea)" />
      <path d={linePath} fill="none" stroke="#1a7a4a" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
      {xs.map((x, i) => (
        <circle
          key={i}
          cx={x} cy={ys[i]}
          r={i === xs.length - 1 ? 5 : 2.5}
          fill={i === xs.length - 1 ? "#1a7a4a" : "white"}
          stroke="#1a7a4a" strokeWidth="1.5"
        />
      ))}
      {[0, 5, 10].map((i) => (
        <text key={i} x={xs[i]} y={h - 10} textAnchor="middle" fontSize="10" fill="#9ca3af" fontFamily="ui-monospace, monospace">
          {2015 + i}
        </text>
      ))}
      <g transform={`translate(${xs[xs.length - 1]}, ${ys[ys.length - 1] - 14})`}>
        <rect x="-18" y="-14" width="36" height="18" rx="9" fill="#0f3d24" />
        <text textAnchor="middle" y="-1" fontSize="11" fontWeight="700" fill="white" fontFamily="ui-monospace, monospace">4.8</text>
      </g>
    </svg>
  );
}
