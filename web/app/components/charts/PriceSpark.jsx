"use client";

/* Mini-serie de precios (últimos ~30 datos). Verde si terminó al alza, azul si a la baja. */
export default function PriceSpark({ values = [], width = 96, height = 28 }) {
  const pts = values.filter((v) => v != null && Number.isFinite(v));
  if (pts.length < 2) {
    return <span className="precios-spark-vacio" title="Sin historial suficiente">—</span>;
  }
  const min = Math.min(...pts);
  const max = Math.max(...pts);
  const rango = max - min || 1;
  const pad = 3;
  const x = (i) => pad + (i * (width - 2 * pad)) / (pts.length - 1);
  const y = (v) => pad + (1 - (v - min) / rango) * (height - 2 * pad);
  const d = pts.map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
  const sube = pts[pts.length - 1] >= pts[0];
  const color = sube ? "#b45309" : "#1e4d7b";

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img"
         aria-label={`Últimos ${pts.length} datos: de ${pts[0]} a ${pts[pts.length - 1]} pesos por kilo`}>
      <path d={d} fill="none" stroke={color} strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={x(pts.length - 1)} cy={y(pts[pts.length - 1])} r="2.6" fill={color} />
    </svg>
  );
}
