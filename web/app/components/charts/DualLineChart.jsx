"use client";

export default function DualLineChart({ height = 280, data = null }) {
  let real, pred, anios;
  if (Array.isArray(data) && data.length > 0) {
    anios = data.map((d) => d.anio);
    real  = data.map((d) => d.real).filter((v) => v != null);
    pred  = data.map((d) => d.predicho ?? null);
  } else {
    real  = [3.4, 3.5, 3.7, 3.6, 3.9, 4.1, 4.2, 4.0, 4.3, 4.6, 4.8];
    pred  = [3.45, 3.55, 3.65, 3.7, 3.85, 4.05, 4.15, 4.1, 4.35, 4.55, 4.78, 4.9, 5.05];
    anios = Array.from({ length: pred.length }, (_, i) => 2015 + i);
  }
  const w = 620, h = height, pad = { l: 40, r: 28, t: 28, b: 36 };
  const allVals = [...real, ...pred].filter((v) => v != null && !Number.isNaN(v));
  const minY = Math.max(0, Math.floor(Math.min(...allVals, 3.2) * 10) / 10 - 0.2);
  const maxY = Math.ceil(Math.max(...allVals, 5.2) * 10) / 10 + 0.2;
  const xs1 = real.map((_, i) => pad.l + (i * (w - pad.l - pad.r)) / (pred.length - 1));
  const ys1 = real.map((v) => pad.t + (1 - (v - minY) / (maxY - minY)) * (h - pad.t - pad.b));
  const xs2 = pred.map((_, i) => pad.l + (i * (w - pad.l - pad.r)) / (pred.length - 1));
  const ys2 = pred.map((v) => pad.t + (1 - (v - minY) / (maxY - minY)) * (h - pad.t - pad.b));
  const realPath = xs1.map((x, i) => `${i === 0 ? "M" : "L"}${x} ${ys1[i]}`).join(" ");
  const predPath = xs2.map((x, i) => `${i === 0 ? "M" : "L"}${x} ${ys2[i]}`).join(" ");
  const forecastStart = xs2[real.length - 1];
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} style={{ display: "block" }}>
      <defs>
        <linearGradient id="forecastFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1e4d7b" stopOpacity="0.10" />
          <stop offset="100%" stopColor="#1e4d7b" stopOpacity="0" />
        </linearGradient>
      </defs>
      <rect x={forecastStart} y={pad.t} width={xs2[xs2.length - 1] - forecastStart} height={h - pad.t - pad.b} fill="url(#forecastFill)" />
      <text x={forecastStart + 6} y={pad.t + 12} fontSize="10" fill="#1e4d7b" fontFamily="ui-monospace, monospace" letterSpacing="0.06em">PRONÓSTICO</text>
      {[3.5, 4.0, 4.5, 5.0].map((v, i) => {
        const y = pad.t + (1 - (v - minY) / (maxY - minY)) * (h - pad.t - pad.b);
        return (
          <g key={i}>
            <line x1={pad.l} x2={w - pad.r} y1={y} y2={y} stroke="#e5e7eb" strokeDasharray="2 4" />
            <text x={pad.l - 8} y={y + 3} fontSize="10" fill="#9ca3af" textAnchor="end" fontFamily="ui-monospace, monospace">{v.toFixed(1)}</text>
          </g>
        );
      })}
      {[0, Math.floor(pred.length / 3), Math.floor((pred.length * 2) / 3), pred.length - 1]
        .filter((i, k, arr) => i >= 0 && i < pred.length && arr.indexOf(i) === k)
        .map((i) => (
          <text key={i} x={xs2[i]} y={h - 12} fontSize="10" fill="#9ca3af" textAnchor="middle" fontFamily="ui-monospace, monospace">
            {anios[i] ?? 2015 + i}
          </text>
        ))}
      <path d={predPath} fill="none" stroke="#1e4d7b" strokeWidth="2" strokeDasharray="5 4" strokeLinejoin="round" />
      <path d={realPath} fill="none" stroke="#1a7a4a" strokeWidth="2.5" strokeLinejoin="round" />
      {xs1.map((x, i) => (
        <circle key={i} cx={x} cy={ys1[i]} r="3" fill="#1a7a4a" stroke="white" strokeWidth="1" />
      ))}
      <g transform={`translate(${pad.l}, 14)`}>
        <rect x="-4" y="-10" width="160" height="18" rx="9" fill="white" stroke="#e5e7eb" />
        <line x1="6" x2="20" y1="0" y2="0" stroke="#1a7a4a" strokeWidth="2.5" />
        <text x="26" y="4" fontSize="11" fill="#374151" fontWeight="500">Real</text>
        <line x1="78" x2="92" y1="0" y2="0" stroke="#1e4d7b" strokeWidth="2" strokeDasharray="5 4" />
        <text x="98" y="4" fontSize="11" fill="#374151" fontWeight="500">Predicho</text>
      </g>
    </svg>
  );
}
