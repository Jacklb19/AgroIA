import pool from "@/lib/db";
import { errorBD, redondear, sinDatos } from "@/lib/api";
import { NOTA_REGLAS, ajusteEscenario } from "@/lib/reglas";

export const dynamic = "force-dynamic";

const MAX_TEXTO = 120;

/* Predicción de rendimiento (t/ha) guardada por el modelo para un municipio y cultivo.
   Sin datos -> 404 "no disponible". Nunca se calcula un valor de reemplazo. */
export async function POST(request) {
  let body;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "El cuerpo debe ser JSON válido." }, { status: 400 });
  }
  const { muni, cultivo, year, semester, enso = "Neutral", lluvia = "Normal" } = body ?? {};
  if (typeof muni !== "string" || typeof cultivo !== "string" || !muni.trim() || !cultivo.trim()
      || muni.length > MAX_TEXTO || cultivo.length > MAX_TEXTO) {
    return Response.json({ error: "Indica 'muni' y 'cultivo' como texto (máx. 120 caracteres)." }, { status: 400 });
  }

  const nombreMuni = muni.split(",")[0].trim();
  const anioPedido = Number.parseInt(year, 10);

  const SELECT = `
    SELECT t.anio,
           pr.rendimiento_predicho_t_ha    AS yhat,
           pr.intervalo_confianza_inferior AS low,
           pr.intervalo_confianza_superior AS high,
           pr.shap_top                     AS shap_top,
           pa.nivel_riesgo                 AS risk,
           pa.score_probabilidad           AS score,
           fp.rendimiento_t_ha             AS hist
    FROM pred_rendimiento pr
    JOIN dim_municipio m ON pr.id_municipio = m.id_municipio
    JOIN dim_cultivo   c ON pr.id_cultivo   = c.id_cultivo
    JOIN dim_tiempo    t ON pr.id_tiempo    = t.id_tiempo
    LEFT JOIN pred_alerta_climatica pa
      ON pa.id_municipio = pr.id_municipio AND pa.id_tiempo = pr.id_tiempo
    LEFT JOIN fact_produccion_agricola fp
      ON fp.id_municipio = pr.id_municipio AND fp.id_cultivo = pr.id_cultivo AND fp.id_tiempo = pr.id_tiempo
    WHERE m.nombre_municipio ILIKE $1 AND c.nombre_cultivo ILIKE $2
  `;

  try {
    const params = [`%${nombreMuni}%`, `%${cultivo.trim()}%`];
    let rows = [];
    if (Number.isInteger(anioPedido)) {
      ({ rows } = await pool.query(`${SELECT} AND t.anio = $3 ORDER BY t.mes DESC LIMIT 1`, [...params, anioPedido]));
    }
    if (!rows.length) {
      ({ rows } = await pool.query(`${SELECT} ORDER BY t.anio DESC, t.mes DESC LIMIT 1`, params));
    }
    if (!rows.length) {
      return sinDatos("No hay predicciones del modelo para esa combinación de municipio y cultivo.");
    }

    const [{ rows: modelo }] = await Promise.all([
      pool.query(`SELECT (metricas_json->>'mae')::float AS mae, (metricas_json->>'r2')::float AS r2,
                         to_char(fecha_entrenamiento, 'YYYY-MM-DD') AS entrenado
                  FROM model_version WHERE activo AND nombre_modelo LIKE '%rendimiento%'
                  ORDER BY id_version DESC LIMIT 1`),
    ]);

    const row = rows[0];
    const yhat = parseFloat(row.yhat);
    const ajuste = ajusteEscenario(enso, lluvia, yhat);   // regla orientativa proporcional
    const num = (v) => (v != null ? parseFloat(v) : null);
    let shap = null;
    if (row.shap_top) {
      try { shap = typeof row.shap_top === "string" ? JSON.parse(row.shap_top) : row.shap_top; } catch { shap = null; }
    }

    return Response.json({
      fromDB: true,
      muni, cultivo, year, semester,
      anio: row.anio,                                   // año realmente usado (puede diferir del pedido)
      yhat_modelo: redondear(yhat, 2),
      yhat: redondear(yhat + ajuste, 2),
      low:  num(row.low)  != null ? Math.max(0, redondear(num(row.low) + ajuste, 2)) : null,
      high: num(row.high) != null ? redondear(num(row.high) + ajuste, 2) : null,
      risk: row.risk ?? null,
      score: num(row.score),
      hist: num(row.hist),
      shap,
      escenario: { enso, lluvia, ajuste_t_ha: ajuste, nota: ajuste !== 0 ? NOTA_REGLAS : null },
      modelo: modelo[0]
        ? { error_tipico_t_ha: redondear(modelo[0].mae, 2), r2: redondear(modelo[0].r2, 2), entrenado: modelo[0].entrenado }
        : null,
    });
  } catch (err) {
    return errorBD("prediccion", err);
  }
}
