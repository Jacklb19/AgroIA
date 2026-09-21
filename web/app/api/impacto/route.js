import pool from "@/lib/db";
import { CACHE_5MIN, errorBD } from "@/lib/api";

export const dynamic = "force-dynamic";

/* KPIs calculados sobre las tablas reales. Nada de valores de respaldo: si la BD falla, 503. */
export async function GET() {
  try {
    const [munis, cultivos, ha, alertas, alto, rend, preds, modelo, anios] = await Promise.all([
      pool.query("SELECT COUNT(DISTINCT id_municipio)::int AS n FROM fact_produccion_agricola"),
      pool.query("SELECT COUNT(DISTINCT id_cultivo)::int AS n FROM fact_produccion_agricola"),
      pool.query("SELECT COALESCE(SUM(area_sembrada_ha), 0)::bigint AS ha FROM fact_produccion_agricola"),
      pool.query("SELECT COUNT(*)::int AS n FROM pred_alerta_climatica WHERE activa = TRUE"),
      pool.query("SELECT COUNT(*)::int AS n FROM pred_alerta_climatica WHERE activa = TRUE AND nivel_riesgo = 'ALTO'"),
      pool.query("SELECT ROUND(AVG(rendimiento_predicho_t_ha)::numeric, 2) AS p FROM pred_rendimiento"),
      pool.query("SELECT COUNT(*)::int AS n FROM pred_rendimiento"),
      pool.query(`SELECT to_char(MAX(fecha_entrenamiento), 'YYYY-MM-DD') AS f
                  FROM model_version WHERE activo AND nombre_modelo LIKE '%rendimiento%'`),
      pool.query(`SELECT MIN(t.anio)::int AS desde, MAX(t.anio)::int AS hasta
                  FROM fact_produccion_agricola fp JOIN dim_tiempo t ON t.id_tiempo = fp.id_tiempo`),
    ]);

    return Response.json(
      {
        fromDB: true,
        municipios_cubiertos:  munis.rows[0].n,          // con al menos un registro de producción
        cultivos_monitoreados: cultivos.rows[0].n,       // con al menos un registro de producción
        hectareas_cobertura:   Number(ha.rows[0].ha) || 0,
        alertas_activas:       alertas.rows[0].n,
        alertas_alto_riesgo:   alto.rows[0].n,
        predicciones_total:    preds.rows[0].n,
        rendimiento_promedio:  rend.rows[0].p != null ? parseFloat(rend.rows[0].p) : null,
        modelo_actualizado:    modelo.rows[0]?.f ?? null,
        produccion_desde:      anios.rows[0]?.desde ?? null,
        produccion_hasta:      anios.rows[0]?.hasta ?? null,
        /* No hay datos de unidades productivas (CNA) para estimarlos: no se inventa la cifra. */
        productores_potenciales: null,
      },
      { headers: CACHE_5MIN },
    );
  } catch (err) {
    return errorBD("impacto", err);
  }
}
