import pool from "@/lib/db";
import { CACHE_1H, errorBD } from "@/lib/api";

export const dynamic = "force-dynamic";

/* Cultivos con producción registrada. (dim_cultivo también contiene productos de precios SIPSA.) */
export async function GET() {
  try {
    const { rows } = await pool.query(`
      SELECT DISTINCT c.nombre_cultivo
      FROM dim_cultivo c
      WHERE EXISTS (SELECT 1 FROM fact_produccion_agricola fp WHERE fp.id_cultivo = c.id_cultivo)
      ORDER BY c.nombre_cultivo
    `);
    return Response.json(rows.map((r) => r.nombre_cultivo), { headers: CACHE_1H });
  } catch (err) {
    return errorBD("cultivos", err);
  }
}
