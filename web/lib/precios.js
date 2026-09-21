/* Utilidades de la sección Precios. Las utilidades comunes viven en lib/api.js. */
export { CACHE_1MIN, CACHE_5MIN, toId, acotar, redondear, errorBD } from "./api";

/* Fecha de hoy en Colombia (UTC-5, sin horario de verano) como "YYYY-MM-DD". */
export function hoyColombia(ahora = new Date()) {
  return new Date(ahora.getTime() - 5 * 3600 * 1000).toISOString().slice(0, 10);
}

/* Días hábiles (lun-vie) transcurridos entre dos fechas "YYYY-MM-DD" (desde excluido, hasta incluido).
   No conoce festivos: un lunes festivo cuenta como día hábil sin dato. */
export function diasHabilesEntre(desde, hasta) {
  const d = new Date(`${desde}T00:00:00Z`);
  const fin = new Date(`${hasta}T00:00:00Z`);
  let n = 0;
  while (d < fin) {
    d.setUTCDate(d.getUTCDate() + 1);
    const dia = d.getUTCDay();
    if (dia !== 0 && dia !== 6) n += 1;
  }
  return n;
}
