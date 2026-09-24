import pool from "@/lib/db";
import { errorBD, sinDatos } from "@/lib/api";

export const dynamic = "force-dynamic";

/* Sugiere un municipio + cultivo que SÍ tenga predicción real, para que el formulario de Predicción
   no arranque en una combinación vacía (solo el 8% de los pares municipio×cultivo tienen predicción:
   el modelo predice donde hay suficiente historial, no en cualquier combinación con producción). */
export async function GET() {
  try {
    const { rows } = await pool.query(`
      SELECT m.nombre_municipio || ', ' || m.nombre_departamento AS muni,
             c.nombre_cultivo AS cultivo
      FROM pred_rendimiento pr
      JOIN dim_municipio m ON m.id_municipio = pr.id_municipio
      JOIN dim_cultivo   c ON c.id_cultivo   = pr.id_cultivo
      JOIN dim_tiempo    t ON t.id_tiempo    = pr.id_tiempo
      GROUP BY m.nombre_municipio, m.nombre_departamento, c.nombre_cultivo
      ORDER BY COUNT(*) DESC, muni
      LIMIT 1
    `);
    if (!rows.length) return sinDatos("Todavía no hay predicciones del modelo.");
    return Response.json(rows[0]);
  } catch (err) {
    return errorBD("prediccion/default", err);
  }
}
