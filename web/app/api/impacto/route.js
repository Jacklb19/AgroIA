import pool from "@/lib/db";

const FALLBACK = {
  municipios_cubiertos:    1122,
  cultivos_monitoreados:   87,
  hectareas_cobertura:     6_400_000,
  alertas_activas:         0,
  alertas_alto_riesgo:     0,
  productores_potenciales: 2_700_000,
  rendimiento_promedio:    4.42,
  fromDB: false,
};

export async function GET() {
  try {
    const [m, c, h, a, alto, rend] = await Promise.all([
      pool.query("SELECT COUNT(*)::int AS n FROM dim_municipio"),
      pool.query("SELECT COUNT(*)::int AS n FROM dim_cultivo"),
      pool.query("SELECT COALESCE(SUM(area_sembrada_ha), 0)::bigint AS ha FROM fact_produccion_agricola"),
      pool.query("SELECT COUNT(*)::int AS n FROM pred_alerta_climatica WHERE activa = TRUE"),
      pool.query("SELECT COUNT(*)::int AS n FROM pred_alerta_climatica WHERE activa = TRUE AND nivel_riesgo = 'ALTO'"),
      pool.query("SELECT ROUND(AVG(rendimiento_predicho_t_ha)::numeric, 2) AS p FROM pred_rendimiento"),
    ]);

    const productores = await pool
      .query(`SELECT COALESCE(SUM(area_cultivos_permanentes_ha) + SUM(area_cultivos_transitorios_ha), 0)::bigint AS ha
              FROM fact_censo_agropecuario`)
      .then((r) => Number(r.rows[0].ha) || 0)
      .catch(() => 0);

    const hectareas = Number(h.rows[0].ha) || 0;

    return Response.json({
      municipios_cubiertos:    m.rows[0].n,
      cultivos_monitoreados:   c.rows[0].n,
      hectareas_cobertura:     hectareas,
      alertas_activas:         a.rows[0].n,
      alertas_alto_riesgo:     alto.rows[0].n,
      productores_potenciales: productores || Math.round(hectareas / 2.5),
      rendimiento_promedio:    parseFloat(rend.rows[0].p) || 0,
      fromDB: true,
    });
  } catch (err) {
    console.error("[impacto] DB error:", err.message);
    return Response.json(FALLBACK);
  }
}
