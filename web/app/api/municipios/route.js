import pool from "@/lib/db";
import { CACHE_1H, errorBD } from "@/lib/api";

export const dynamic = "force-dynamic";

/* Municipios con producción registrada ("Municipio, Departamento"). Sin listas de respaldo. */
export async function GET() {
  try {
    const { rows } = await pool.query(`
      SELECT DISTINCT m.nombre_municipio || ', ' || m.nombre_departamento AS municipio
      FROM dim_municipio m
      WHERE EXISTS (SELECT 1 FROM fact_produccion_agricola fp WHERE fp.id_municipio = m.id_municipio)
      ORDER BY 1
    `);
    return Response.json(rows.map((r) => r.municipio), { headers: CACHE_1H });
  } catch (err) {
    return errorBD("municipios", err);
  }
}
