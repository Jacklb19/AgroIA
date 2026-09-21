import pool from "@/lib/db";
import { CACHE_5MIN, errorBD } from "@/lib/api";

export const dynamic = "force-dynamic";


export async function GET() {
  try {
    const [tipos, top, semaforo, serie] = await Promise.all([
      pool.query(`
        SELECT COALESCE(tipo_evento, 'Sin clasificar') AS tipo,
               COUNT(*)::int AS total
        FROM pred_alerta_climatica
        WHERE activa = TRUE
        GROUP BY tipo_evento
        ORDER BY total DESC
        LIMIT 6
      `),
      pool.query(`
        SELECT m.nombre_municipio || ', ' || m.nombre_departamento AS municipio,
               ROUND(AVG(pr.rendimiento_predicho_t_ha)::numeric, 2) AS rendimiento
        FROM pred_rendimiento pr
        JOIN dim_municipio m ON m.id_municipio = pr.id_municipio
        GROUP BY m.nombre_municipio, m.nombre_departamento
        ORDER BY rendimiento DESC
        LIMIT 6
      `),
      pool.query(`
        SELECT nivel_riesgo, COUNT(*)::int AS total
        FROM pred_alerta_climatica
        WHERE activa = TRUE
        GROUP BY nivel_riesgo
      `),
      pool.query(`
        -- Real y modelo sobre LAS MISMAS filas (municipio × cultivo × año) y solo predicciones fuera de muestra
        SELECT dt.anio,
               ROUND(AVG(fp.rendimiento_t_ha)::numeric, 2)          AS real,
               ROUND(AVG(pr.rendimiento_predicho_t_ha)::numeric, 2) AS predicho
        FROM pred_rendimiento pr
        JOIN fact_produccion_agricola fp
          ON fp.id_municipio = pr.id_municipio AND fp.id_cultivo = pr.id_cultivo AND fp.id_tiempo = pr.id_tiempo
        JOIN dim_tiempo dt ON dt.id_tiempo = pr.id_tiempo
        WHERE pr.es_holdout = TRUE AND fp.rendimiento_t_ha IS NOT NULL
        GROUP BY dt.anio
        ORDER BY dt.anio
      `),
    ]);

    const anomalias = await pool
      .query(`
        SELECT m.nombre_municipio || ', ' || m.nombre_departamento AS municipio,
               c.nombre_cultivo,
               ROUND(pr.rendimiento_predicho_t_ha::numeric, 2)  AS rendimiento,
               ROUND(pr.anomalia_score::numeric, 3)             AS score
        FROM pred_rendimiento pr
        JOIN dim_municipio m ON m.id_municipio = pr.id_municipio
        JOIN dim_cultivo   c ON c.id_cultivo   = pr.id_cultivo
        WHERE pr.es_anomalia = TRUE
        ORDER BY pr.anomalia_score DESC NULLS LAST
        LIMIT 6
      `)
      .then((r) => r.rows.map((row) => ({
        municipio:    row.municipio,
        cultivo:      row.nombre_cultivo,
        rendimiento:  parseFloat(row.rendimiento),
        score:        parseFloat(row.score),
      })))
      .catch(() => []);

    const totalAlertas = tipos.rows.reduce((s, r) => s + Number(r.total || 0), 0) || 1;
    const alertas_por_tipo = tipos.rows.map((r) => ({
      tipo: r.tipo,
      total: Number(r.total),
      pct: Math.round((Number(r.total) / totalAlertas) * 100),
    }));

    const semaforoMap = { bajo: 0, medio: 0, alto: 0 };
    for (const r of semaforo.rows) {
      const k = String(r.nivel_riesgo || "").toLowerCase();
      if (k in semaforoMap) semaforoMap[k] = Number(r.total);
    }

    return Response.json({
      fromDB: true,
      alertas_por_tipo,
      top_municipios: top.rows.map((r) => ({
        municipio:    r.municipio,
        rendimiento:  parseFloat(r.rendimiento),
      })),
      semaforo: semaforoMap,
      serie_rendimiento: serie.rows.map((r) => ({
        anio:     Number(r.anio),
        real:     r.real     != null ? parseFloat(r.real)     : null,
        predicho: r.predicho != null ? parseFloat(r.predicho) : null,
      })),
      anomalias,
    }, { headers: CACHE_5MIN });
  } catch (err) {
    return errorBD("dashboards", err);
  }
}
