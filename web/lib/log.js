import crypto from "crypto";

/* Logs en una línea JSON (los agregan bien Vercel, Railway y cualquier drain) con un request_id para
   seguir una petición de punta a punta. Nunca registres secretos, IPs ni el texto completo de los mensajes. */

export function requestId(request) {
  const h = request?.headers;
  return h?.get("x-request-id") || h?.get("x-vercel-id") || crypto.randomUUID();
}

export function log(nivel, evento, campos = {}) {
  const linea = JSON.stringify({ t: new Date().toISOString(), nivel, evento, ...campos });
  if (nivel === "error") console.error(linea);
  else if (nivel === "warn") console.warn(linea);
  else console.log(linea);
}

/* Envuelve un handler: añade x-request-id a la respuesta y registra estado y duración. */
export function conRegistro(nombre, handler) {
  return async function registrado(request, ctx) {
    const rid = requestId(request);
    const t0 = Date.now();
    let res;
    try {
      res = await handler(request, ctx, rid);
    } catch (err) {
      log("error", nombre, { request_id: rid, mensaje: err?.message, ms: Date.now() - t0 });
      res = Response.json({ error: "Error interno.", request_id: rid }, { status: 500 });
    }
    res.headers.set("x-request-id", rid);
    log(res.status >= 500 ? "error" : "info", nombre, { request_id: rid, status: res.status, ms: Date.now() - t0 });
    return res;
  };
}
