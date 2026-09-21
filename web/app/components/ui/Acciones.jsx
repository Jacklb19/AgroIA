"use client";
import { useState } from "react";
import { descargarCsv } from "@/lib/csv";

/* Barra de acciones de una tabla: descargar CSV y copiar el enlace de la vista actual (con sus filtros). */
export default function Acciones({ nombreArchivo, columnas, filas, deshabilitado }) {
  const [copiado, setCopiado] = useState(false);

  const copiar = async () => {
    const url = window.location.href;
    try {
      await navigator.clipboard.writeText(url);
    } catch {
      window.prompt("Copia este enlace:", url);   // navegadores sin permiso de portapapeles
      return;
    }
    setCopiado(true);
    setTimeout(() => setCopiado(false), 2000);
  };

  return (
    <div className="acciones">
      <button type="button" className="accion-btn" disabled={deshabilitado || !filas?.length}
              onClick={() => descargarCsv(nombreArchivo, columnas, filas)}>
        Descargar CSV
      </button>
      <button type="button" className="accion-btn" onClick={copiar}>Copiar enlace</button>
      <span className="acciones-estado" role="status" aria-live="polite">{copiado ? "Enlace copiado" : ""}</span>
    </div>
  );
}
