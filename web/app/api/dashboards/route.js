import pool from "@/lib/db";

const FALLBACK = {
  fromDB: false,
  alertas_por_tipo: [
    { tipo: "Sequía severa",         total: 43, pct: 43 },
    { tipo: "Exceso de lluvias",     total: 31, pct: 31 },
    { tipo: "Plagas y enfermedades", total: 18, pct: 18 },
    { tipo: "Volatilidad mercado",   total:  8, pct:  8 },
  ],
  top_municipios: [
    { municipio: "Espinal, Tolima",  rendimiento: 6.2 },
    { municipio: "Saldaña, Tolima",  rendimiento: 5.9 },
    { municipio: "Aipe, Huila",      rendimiento: 5.6 },
    { municipio: "Yopal, Casanare",  rendimiento: 5.4 },
    { municipio: "Granada, Meta",    rendimiento: 5.1 },
    { municipio: "Ibagué, Tolima",   rendimiento: 4.8 },
  ],
  semaforo: { bajo: 51, medio: 31, alto: 18 },
  serie_rendimiento: [
    { anio: 2018, real: 4.0, predicho: 4.1 },
    { anio: 2019, real: 4.1, predicho: 4.2 },
    { anio: 2020, real: 3.9, predicho: 4.0 },
    { anio: 2021, real: 4.3, predicho: 4.4 },
    { anio: 2022, real: 4.5, predicho: 4.5 },
    { anio: 2023, real: 4.6, predicho: 4.7 },
    { anio: 2024, real: 4.7, predicho: 4.8 },
    { anio: 2025, real: null, predicho: 4.9 },
    { anio: 2026, real: null, predicho: 5.0 },
  ],
  anomalias: [],
};

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
        SELECT dt.anio,
               ROUND(AVG(fp.rendimiento_t_ha)::numeric, 2)         AS real,
               ROUND(AVG(pr.rendimiento_predicho_t_ha)::numeric, 2) AS predicho
        FROM dim_tiempo dt
        LEFT JOIN fact_produccion_agricola fp ON fp.id_tiempo = dt.id_tiempo
        LEFT JOIN pred_rendimiento pr         ON pr.id_tiempo = dt.id_tiempo
        WHERE dt.mes = 12
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
    });
  } catch (err) {
    console.error("[dashboards] DB error:", err.message);
    return Response.json(FALLBACK);
  }
}
