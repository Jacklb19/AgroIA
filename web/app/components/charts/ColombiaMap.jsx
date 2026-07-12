"use client";

const RIESGO_COLOR = { ALTO: "#dc2626", MEDIO: "#d97706", BAJO: "#1a7a4a" };

/* Bounding box aproximado del territorio continental colombiano */
const BBOX = { minLon: -79.5, maxLon: -66.5, minLat: -4.5, maxLat: 13.5 };
/* Caja útil dentro del viewBox (320×290) tras el path del país */
const BOX  = { x0: 60, y0: 25, x1: 275, y1: 275 };

function projectLatLon(lat, lon) {
  const x = BOX.x0 + ((lon - BBOX.minLon) / (BBOX.maxLon - BBOX.minLon)) * (BOX.x1 - BOX.x0);
  const y = BOX.y1 - ((lat - BBOX.minLat) / (BBOX.maxLat - BBOX.minLat)) * (BOX.y1 - BOX.y0);
  return { x, y };
}

export default function ColombiaMap({ pins = [], puntos = null, height = 280 }) {
  const path =
    "M 95 30 L 130 22 L 165 32 L 195 28 L 222 48 L 248 56 L 262 82 L 252 112 L 272 138 L 268 168 L 248 198 L 238 224 L 212 248 L 178 268 L 152 274 L 132 264 L 112 244 L 96 218 L 80 196 L 65 175 L 58 145 L 70 113 L 86 88 L 92 58 Z";

  const computedPins = (Array.isArray(puntos) && puntos.length > 0)
    ? puntos.map((p) => {
        const { x, y } = projectLatLon(p.lat, p.lon);
        return {
          x, y,
          color: RIESGO_COLOR[p.riesgo] || "#6b7280",
          label: `${p.municipio || ""}${p.departamento ? `, ${p.departamento}` : ""}`,
        };
      })
    : pins;

  return (
    <svg viewBox="0 0 320 290" width="100%" height={height} style={{ display: "block" }}>
      <defs>
        <linearGradient id="colFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#22a35f" stopOpacity="0.16" />
          <stop offset="100%" stopColor="#155436" stopOpacity="0.36" />
        </linearGradient>
        <filter id="pinGlow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="2.5" />
        </filter>
      </defs>
      <path d={path} fill="url(#colFill)" stroke="#155436" strokeWidth="1.4" strokeOpacity="0.45" />
      <path
        d="M 160 50 Q 175 110 165 170 T 175 250"
        fill="none"
        stroke="#1e4d7b"
        strokeWidth="1"
        strokeOpacity="0.35"
        strokeDasharray="2 3"
      />
      {computedPins.map((p, i) => (
        <g key={i}>
          {p.label && <title>{p.label}</title>}
          <circle cx={p.x} cy={p.y} r="8" fill={p.color} fillOpacity="0.18" filter="url(#pinGlow)" />
          <circle cx={p.x} cy={p.y} r="6" fill={p.color} fillOpacity="0.22" />
          <circle cx={p.x} cy={p.y} r="3.5" fill={p.color} stroke="white" strokeWidth="1.2" />
        </g>
      ))}
    </svg>
  );
}
