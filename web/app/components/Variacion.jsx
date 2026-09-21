"use client";
import { pct } from "@/lib/formatoPrecios";

/* Variación porcentual con flecha. Colores neutros (ámbar sube, azul baja): subir no es "bueno" ni "malo"
   para todos (al productor le conviene, al comprador no). */
export default function Variacion({ v }) {
  if (v == null) return <span className="var-flat">—</span>;
  if (Math.abs(v) < 0.05) return <span className="var-flat">0,0 %</span>;
  return v > 0
    ? <span className="var-up" title="Subió">▲ +{pct(v)} %</span>
    : <span className="var-down" title="Bajó">▼ {pct(v)} %</span>;
}
