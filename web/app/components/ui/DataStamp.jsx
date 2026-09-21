"use client";

/* Línea de trazabilidad para cada tarjeta: de dónde sale el dato y de cuándo es. */
export default function DataStamp({ fuente, fecha, nota }) {
  return (
    <div className="data-stamp">
      <span>Fuente: <strong>{fuente}</strong></span>
      {fecha && <span>· Dato de: {fecha}</span>}
      {nota && <span>· {nota}</span>}
    </div>
  );
}
