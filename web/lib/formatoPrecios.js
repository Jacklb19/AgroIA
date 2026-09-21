/* Formato de precios y fechas para la sección Precios (es-CO, hora de Bogotá). */

export const cop = (v) => (v == null ? "—" : `$ ${Math.round(v).toLocaleString("es-CO")}`);

export const pct = (v) => v.toLocaleString("es-CO", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

/* "2026-09-18" -> "vie, 18 de sept" */
export const fechaCorta = (iso) =>
  iso ? new Date(`${iso}T12:00:00Z`).toLocaleDateString("es-CO", { timeZone: "UTC", weekday: "short", day: "numeric", month: "short" }) : "—";

export const fechaLarga = (iso) =>
  iso ? new Date(`${iso}T12:00:00Z`).toLocaleDateString("es-CO", { timeZone: "UTC", weekday: "long", day: "numeric", month: "long", year: "numeric" }) : "—";

export const hora = (iso) =>
  iso ? new Date(iso).toLocaleTimeString("es-CO", { timeZone: "America/Bogota", hour: "2-digit", minute: "2-digit" }) : "—";
