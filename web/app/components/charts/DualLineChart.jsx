"use client";
import { EmptyState } from "../ui/Estados";

/* Serie anual real vs. modelo. Solo dibuja los datos recibidos: sin datos de demostración.
   data: [{ anio, real, predicho }]  (real o predicho pueden ser null) */
export default function DualLineChart({ height = 280, data = [] }) {
  const puntos = (Array.isArray(data) ? data : []).filter((d) => d && d.anio != null && (d.real != null || d.predicho != null));
  if (puntos.length < 2) {
    return <EmptyState titulo="Serie no disponible" texto="Todavía no hay suficientes años con datos para graficar." />;
  }

  const w = 620, h = height, pad = { l: 44, r: 28, t: 28, b: 36 };
  const valores = puntos.flatMap((d) => [d.real, d.predicho]).filter((v) => v != null && Number.isFinite(v));
  const vmin = Math.min(...valores), vmax = Math.max(...valores);
  const margen = (vmax - vmin || Math.abs(vmax) || 1) * 0.12;
  const minY = Math.max(0, vmin - margen), maxY = vmax + margen;

  const X = (i) => pad.l + (i * (w - pad.l - pad.r)) / (puntos.length - 1);
  const Y = (v) => pad.t + (1 - (v - minY) / (maxY - minY)) * (h - pad.t - pad.b);
  const trazo = (clave) => {
    let d = "";
    puntos.forEach((p, i) => {
      if (p[clave] == null) return;
      d += `${d ? "L" : "M"}${X(i).toFixed(1)} ${Y(p[clave]).toFixed(1)} `;
    });
    return d;
  };

  const ticksY = [0, 1, 2, 3].map((i) => minY + ((maxY - minY) * i) / 3);
  const idxTicks = [...new Set([0, Math.floor((puntos.length - 1) / 3), Math.floor(((puntos.length - 1) * 2) / 3), puntos.length - 1])];
  const primeraSinReal = puntos.findIndex((p) => p.real == null);
  const inicioFuturo = primeraSinReal > 0 ? X(primeraSinReal - 1) : null;

  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} style={{ display: "block" }} role="img"
         aria-label={`Rendimiento medio por año, real y del modelo, de ${puntos[0].anio} a ${puntos[puntos.length - 1].anio}`}>
      {inicioFuturo != null && (
        <>
          <rect x={inicioFuturo} y={pad.t} width={X(puntos.length - 1) - inicioFuturo} height={h - pad.t - pad.b} fill="#1e4d7b" fillOpacity="0.06" />
          <text x={inicioFuturo + 6} y={pad.t + 12} fontSize="10" fill="#1e4d7b" fontFamily="ui-monospace, monospace" letterSpacing="0.06em">SIN DATO REAL</text>
        </>
      )}
      {ticksY.map((v, i) => (
        <g key={i}>
          <line x1={pad.l} x2={w - pad.r} y1={Y(v)} y2={Y(v)} stroke="#e5e7eb" strokeDasharray="2 4" />
          <text x={pad.l - 8} y={Y(v) + 3} fontSize="10" fill="#6b7280" textAnchor="end" fontFamily="ui-monospace, monospace">{v.toFixed(v < 10 ? 1 : 0)}</text>
        </g>
      ))}
      {idxTicks.map((i) => (
        <text key={i} x={X(i)} y={h - 12} fontSize="10" fill="#6b7280" textAnchor="middle" fontFamily="ui-monospace, monospace">{puntos[i].anio}</text>
      ))}
      <path d={trazo("predicho")} fill="none" stroke="#1e4d7b" strokeWidth="2" strokeDasharray="5 4" strokeLinejoin="round" />
      <path d={trazo("real")} fill="none" stroke="#1a7a4a" strokeWidth="2.5" strokeLinejoin="round" />
      {puntos.map((p, i) => p.real != null && <circle key={i} cx={X(i)} cy={Y(p.real)} r="3" fill="#1a7a4a" stroke="white" strokeWidth="1" />)}
      <g transform={`translate(${pad.l}, 14)`}>
        <rect x="-4" y="-10" width="150" height="18" rx="9" fill="white" stroke="#e5e7eb" />
        <line x1="6" x2="20" y1="0" y2="0" stroke="#1a7a4a" strokeWidth="2.5" />
        <text x="26" y="4" fontSize="11" fill="#374151" fontWeight="500">Real</text>
        <line x1="68" x2="82" y1="0" y2="0" stroke="#1e4d7b" strokeWidth="2" strokeDasharray="5 4" />
        <text x="88" y="4" fontSize="11" fill="#374151" fontWeight="500">Modelo</text>
      </g>
    </svg>
  );
}
