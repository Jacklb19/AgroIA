"use client";
import { useId } from "react";
import { GLOSARIO } from "@/lib/glosario";

/* Término con definición: <Term id="p10-p90">p10–p90</Term>.
   Accesible con teclado (foco) y lectores de pantalla (aria-describedby); en táctil se abre al tocar (foco). */
export default function Term({ id, children }) {
  const entrada = GLOSARIO[id];
  const tipId = useId();
  if (!entrada) return <>{children ?? id}</>;
  return (
    <span className="term" tabIndex={0} aria-describedby={tipId}>
      {children ?? entrada.termino}
      <span role="tooltip" id={tipId} className="term-tip">
        <strong>{entrada.termino}</strong> — {entrada.definicion}
      </span>
    </span>
  );
}
