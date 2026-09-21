/* CSV (RFC 4180, coma). Sirve en el servidor (?formato=csv) y en el navegador (botón "Descargar CSV"). */

/* Una celda que empieza por = + - @ se interpretaría como fórmula en Excel; se neutraliza con una comilla. */
function celda(valor) {
  if (valor == null) return "";
  let s = String(valor);
  if (typeof valor !== "number" && /^[=+\-@\t\r]/.test(s)) s = `'${s}`;
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/* columnas: [{ clave, titulo }]; filas: objetos. Devuelve el texto CSV (sin BOM). */
export function aCsv(columnas, filas) {
  const cab = columnas.map((c) => celda(c.titulo)).join(",");
  const cuerpo = filas.map((f) => columnas.map((c) => celda(f[c.clave])).join(","));
  return [cab, ...cuerpo].join("\r\n") + "\r\n";
}

/* Solo navegador. Con BOM para que Excel reconozca UTF-8 (tildes, ñ). */
export function descargarCsv(nombre, columnas, filas) {
  const blob = new Blob(["﻿", aCsv(columnas, filas)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nombre.endsWith(".csv") ? nombre : `${nombre}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function respuestaCsv(nombre, columnas, filas) {
  return new Response("﻿" + aCsv(columnas, filas), {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="${nombre}.csv"`,
      "Cache-Control": "public, s-maxage=60, stale-while-revalidate=120",
    },
  });
}
