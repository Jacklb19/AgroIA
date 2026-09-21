import pool from "@/lib/db";
import { log } from "@/lib/log";

export const dynamic = "force-dynamic";

/* Healthcheck para monitoreo. No expone detalles internos de la BD (mensajes, códigos ni nombre de la base). */
export async function GET() {
  const inicio = Date.now();
  try {
    await pool.query("SELECT 1");
    return Response.json({ ok: true, latencia_ms: Date.now() - inicio }, { headers: { "Cache-Control": "no-store" } });
  } catch (err) {
    log("error", "health", { mensaje: err?.message, codigo: err?.code });
    return Response.json({ ok: false }, { status: 503, headers: { "Cache-Control": "no-store" } });
  }
}
