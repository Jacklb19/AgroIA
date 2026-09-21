"use client";
import { useMemo, useRef, useState } from "react";

const W = 720;
const PAD = { l: 64, r: 20, t: 20, b: 34 };

const cop = (v) => (v == null ? "—" : `$ ${Math.round(v).toLocaleString("es-CO")}`);
const dia = (iso) =>
  new Date(`${iso}T12:00:00Z`).toLocaleDateString("es-CO", { timeZone: "UTC", weekday: "short", day: "numeric", month: "short", year: "numeric" });
const diaCorto = (iso) =>
  new Date(`${iso}T12:00:00Z`).toLocaleDateString("es-CO", { timeZone: "UTC", day: "numeric", month: "short", year: "2-digit" });
const ms = (iso) => new Date(`${iso}T12:00:00Z`).getTime();

/* Historial (línea verde + banda mín–máx) y pronóstico (línea azul discontinua + banda p10–p90).
   serie: [{fecha, prom, min, max}]   prediccion: [{fecha, precio, p10, p90}] */
export default function PriceChart({ serie = [], prediccion = [], height = 320 }) {
  const svgRef = useRef(null);
  const [hover, setHover] = useState(null);

  const g = useMemo(() => {
    const todos = [...serie.map((d) => ms(d.fecha)), ...prediccion.map((d) => ms(d.fecha))];
    if (!todos.length) return null;
    const x0 = Math.min(...todos);
    const x1 = Math.max(...todos);
    const vals = [
      ...serie.flatMap((d) => [d.prom, d.min, d.max]),
      ...prediccion.flatMap((d) => [d.precio, d.p10, d.p90]),
    ].filter((v) => v != null && Number.isFinite(v));
    const vmin = Math.min(...vals);
    const vmax = Math.max(...vals);
    const margen = (vmax - vmin || vmax || 1) * 0.08;
    const y0 = Math.max(0, vmin - margen);
    const y1 = vmax + margen;
    const X = (t) => PAD.l + ((t - x0) / (x1 - x0 || 1)) * (W - PAD.l - PAD.r);
    const Y = (v) => PAD.t + (1 - (v - y0) / (y1 - y0)) * (height - PAD.t - PAD.b);
    return { x0, x1, y0, y1, X, Y };
  }, [serie, prediccion, height]);

  if (!g) return <div className="precios-vacio">Sin datos para graficar.</div>;

  const { X, Y } = g;
  const linea = (pts, clave) =>
    pts.filter((d) => d[clave] != null)
       .map((d, i) => `${i === 0 ? "M" : "L"}${X(ms(d.fecha)).toFixed(1)} ${Y(d[clave]).toFixed(1)}`).join(" ");
  const banda = (pts, lo, hi) => {
    const v = pts.filter((d) => d[lo] != null && d[hi] != null);
    if (v.length < 2) return "";
    const arriba = v.map((d, i) => `${i === 0 ? "M" : "L"}${X(ms(d.fecha)).toFixed(1)} ${Y(d[hi]).toFixed(1)}`);
    const abajo = [...v].reverse().map((d) => `L${X(ms(d.fecha)).toFixed(1)} ${Y(d[lo]).toFixed(1)}`);
    return `${arriba.join(" ")} ${abajo.join(" ")} Z`;
  };

  const ticksY = [0, 1, 2, 3].map((i) => g.y0 + ((g.y1 - g.y0) * i) / 3);
  const ticksX = [0, 1, 2, 3].map((i) => g.x0 + ((g.x1 - g.x0) * i) / 3);

  /* Puntos consultables con el mouse/tacto (historial + pronóstico) */
  const puntos = [
    ...serie.map((d) => ({ fecha: d.fecha, valor: d.prom, min: d.min, max: d.max, tipo: "real" })),
    ...prediccion.map((d) => ({ fecha: d.fecha, valor: d.precio, min: d.p10, max: d.p90, tipo: "pronostico" })),
  ];
  const onMove = (e) => {
    const r = svgRef.current.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    let mejor = null;
    for (const p of puntos) {
      const dx = Math.abs(X(ms(p.fecha)) - px);
      if (!mejor || dx < mejor.dx) mejor = { ...p, dx };
    }
    setHover(mejor);
  };

  const ultimo = serie[serie.length - 1];
  const hoverX = hover ? X(ms(hover.fecha)) : null;

  return (
    <div className="precios-chart">
      <svg ref={svgRef} viewBox={`0 0 ${W} ${height}`} width="100%" height={height} style={{ display: "block" }}
           role="img" aria-label={`Precio por kilo. Último dato ${ultimo ? cop(ultimo.prom) : "no disponible"}.`}
           onMouseMove={onMove} onMouseLeave={() => setHover(null)} onTouchMove={(e) => onMove(e.touches[0])}>
        {ticksY.map((v, i) => (
          <g key={i}>
            <line x1={PAD.l} x2={W - PAD.r} y1={Y(v)} y2={Y(v)} stroke="#e5e7eb" strokeDasharray="2 4" />
            <text x={PAD.l - 8} y={Y(v) + 3} fontSize="10.5" fill="#6b7280" textAnchor="end" fontFamily="ui-monospace, monospace">
              {Math.round(v).toLocaleString("es-CO")}
            </text>
          </g>
        ))}
        {ticksX.map((t, i) => (
          <text key={i} x={X(t)} y={height - 10} fontSize="10.5" fill="#6b7280"
                textAnchor={i === 0 ? "start" : i === ticksX.length - 1 ? "end" : "middle"} fontFamily="ui-monospace, monospace">
            {diaCorto(new Date(t).toISOString().slice(0, 10))}
          </text>
        ))}

        <path d={banda(serie, "min", "max")} fill="#22a35f" fillOpacity="0.12" />
        <path d={banda(prediccion, "p10", "p90")} fill="#1e4d7b" fillOpacity="0.14" />
        <path d={linea(serie, "prom")} fill="none" stroke="#1a7a4a" strokeWidth="2.2" strokeLinejoin="round" />
        {prediccion.length > 0 && ultimo && (
          <path d={`M${X(ms(ultimo.fecha)).toFixed(1)} ${Y(ultimo.prom).toFixed(1)} ${linea(prediccion, "precio").replace(/^M/, "L")}`}
                fill="none" stroke="#1e4d7b" strokeWidth="2" strokeDasharray="5 4" strokeLinejoin="round" />
        )}
        {ultimo && <circle cx={X(ms(ultimo.fecha))} cy={Y(ultimo.prom)} r="4.5" fill="#1a7a4a" stroke="white" strokeWidth="1.5" />}

        {hover && (
          <g pointerEvents="none">
            <line x1={hoverX} x2={hoverX} y1={PAD.t} y2={height - PAD.b} stroke="#9ca3af" strokeWidth="1" />
            <circle cx={hoverX} cy={Y(hover.valor)} r="4" fill={hover.tipo === "real" ? "#1a7a4a" : "#1e4d7b"} stroke="white" strokeWidth="1.5" />
          </g>
        )}
      </svg>

      <div className="precios-chart-leyenda" aria-live="polite">
        {hover ? (
          <>
            <strong>{dia(hover.fecha)}</strong>{" "}
            {hover.tipo === "pronostico" ? "· pronóstico " : "· "}
            <strong>{cop(hover.valor)}</strong>/kg
            {hover.min != null && hover.max != null && <span> · rango {cop(hover.min)} – {cop(hover.max)}</span>}
          </>
        ) : (
          <>
            <span className="leyenda-item"><i style={{ background: "#1a7a4a" }} /> Precio promedio</span>
            <span className="leyenda-item"><i style={{ background: "#22a35f", opacity: 0.3 }} /> Rango mín–máx del día</span>
            {prediccion.length > 0 && <span className="leyenda-item"><i style={{ background: "#1e4d7b" }} /> Pronóstico (banda p10–p90)</span>}
          </>
        )}
      </div>
    </div>
  );
}
