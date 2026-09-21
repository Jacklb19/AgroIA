import pool from "@/lib/db";
import { CACHE_5MIN, errorBD } from "@/lib/api";

export const dynamic = "force-dynamic";

/* Municipios con coordenadas y su nivel de riesgo vigente. Solo municipios con una alerta
   activa (no se asume "BAJO" para los demás) y en orden determinista: primero los de mayor probabilidad. */
export async function GET() {
  try {
    const { rows } = await pool.query(`
      SELECT m.nombre_municipio, m.nombre_departamento,
             m.latitud_centroide  AS lat,
             m.longitud_centroide AS lon,
             a.nivel_riesgo       AS riesgo
      FROM dim_municipio m
      JOIN LATERAL (
        SELECT pa.nivel_riesgo, pa.score_probabilidad
        FROM pred_alerta_climatica pa
        WHERE pa.id_municipio = m.id_municipio AND pa.activa = TRUE
        ORDER BY pa.score_probabilidad DESC NULLS LAST
        LIMIT 1
      ) a ON TRUE
      WHERE m.latitud_centroide IS NOT NULL AND m.longitud_centroide IS NOT NULL
        AND m.latitud_centroide <> 0
      ORDER BY a.score_probabilidad DESC NULLS LAST, m.nombre_municipio
      LIMIT 120
    `);
    return Response.json(
      rows.map((r) => ({
        municipio:    r.nombre_municipio,
        departamento: r.nombre_departamento,
        lat:          parseFloat(r.lat),
        lon:          parseFloat(r.lon),
        riesgo:       r.riesgo,
      })),
      { headers: CACHE_5MIN },
    );
  } catch (err) {
    return errorBD("mapa", err);
  }
}
