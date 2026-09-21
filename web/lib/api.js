import { log, requestId } from "./log";

/* Utilidades compartidas por todas las rutas /api/*.
   Regla del proyecto: nunca se inventan datos. Si la base de datos falla, se responde 503
   (sin exponer el error interno) y la interfaz muestra un estado vacío. */

export const CACHE_1MIN = { "Cache-Control": "public, s-maxage=60, stale-while-revalidate=120" };
export const CACHE_5MIN = { "Cache-Control": "public, s-maxage=300, stale-while-revalidate=600" };
export const CACHE_1H   = { "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=7200" };

/* Entero positivo o null (para ids que llegan por query string). */
export function toId(valor) {
  const n = Number(valor);
  return Number.isInteger(n) && n > 0 ? n : null;
}

/* Entero acotado a [min, max]; null/vacío/no numérico -> defecto (Number(null) sería 0). */
export function acotar(valor, min, max, defecto) {
  if (valor == null || valor === "") return defecto;
  const n = Number(valor);
  if (!Number.isFinite(n)) return defecto;
  return Math.min(max, Math.max(min, Math.trunc(n)));
}

export const redondear = (v, d = 1) => (v == null ? null : Math.round(Number(v) * 10 ** d) / 10 ** d);

/* 503 uniforme: no expone el mensaje interno de la BD ni inventa datos. El detalle va al log del servidor
   (JSON) y el cliente recibe solo un request_id para poder reportarlo. */
export function errorBD(etiqueta, err, request) {
  const rid = requestId(request);
  log("error", etiqueta, { request_id: rid, mensaje: err?.message, codigo: err?.code });
  return Response.json(
    { fromDB: false, error: "Los datos no están disponibles en este momento.", request_id: rid },
    { status: 503, headers: { "x-request-id": rid } },
  );
}

/* 404 uniforme cuando la consulta funcionó pero no hay datos para lo pedido. */
export function sinDatos(mensaje, extra = {}) {
  return Response.json({ fromDB: true, disponible: false, mensaje, ...extra }, { status: 404 });
}
