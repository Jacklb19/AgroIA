import pool from "@/lib/db";
import { CACHE_5MIN, acotar, errorBD, redondear, toId } from "@/lib/precios";

export const dynamic = "force-dynamic";

/* Serie histórica de un producto en un mercado (+ pronóstico si existe).
   /api/precios/serie?producto=<id>&mercado=<id>&dias=90 */
export async function GET(request) {
  const sp = new URL(request.url).searchParams;
  const producto = toId(sp.get("producto"));
  const mercado = toId(sp.get("mercado"));
  const dias = acotar(sp.get("dias"), 7, 2200, 90);

  if (!producto || !mercado) {
    return Response.json({ error: "Parámetros 'producto' y 'mercado' (ids) son obligatorios." }, { status: 400 });
  }

  try {
    const [meta, serie, pred, calidad] = await Promise.all([
      pool.query(
        `SELECT p.nombre AS producto, ca.nombre_central AS mercado, ca.ciudad, ca.nombre_departamento AS departamento
         FROM dim_producto_precio p, dim_central_abastos ca
         WHERE p.id_producto = $1 AND ca.id_central = $2`,
        [producto, mercado],
      ),
      pool.query(
        `SELECT to_char(fecha, 'YYYY-MM-DD') AS fecha, precio_prom_kg, precio_min_kg, precio_max_kg
         FROM fact_precio_diario
         WHERE id_producto = $1 AND id_central = $2 AND fecha >= CURRENT_DATE - $3::int
         ORDER BY fecha`,
        [producto, mercado, dias],
      ),
      pool.query(
        `SELECT to_char(fecha_objetivo, 'YYYY-MM-DD') AS fecha, horizonte_dias,
                precio_pred_kg, p10_kg, p90_kg, confianza, metodo
         FROM pred_precio
         WHERE id_producto = $1 AND id_central = $2 AND fecha_objetivo >= CURRENT_DATE
         ORDER BY fecha_objetivo`,
        [producto, mercado],
      ),
      /* Calidad del pronóstico en el backtest (errores en escala logarítmica ≈ error relativo). */
      pool.query(
        `SELECT metricas_json->'por_producto'->($1::int)::text AS q,
                metricas_json->'backtest'->'n_test' AS n_test,
                metricas_json->>'entrenado_hasta' AS entrenado_hasta
         FROM model_version
         WHERE nombre_modelo = 'xgboost_precio_diario' AND activo
         ORDER BY id_version DESC LIMIT 1`,
        [producto],
      ),
    ]);

    if (!meta.rows.length) {
      return Response.json({ error: "Producto o mercado no encontrado." }, { status: 404 });
    }

    const q = calidad.rows[0]?.q ?? null;
    return Response.json(
      {
        fromDB: true,
        ...meta.rows[0],
        calidad_pronostico: q && {
          error_modelo_pct:  redondear(q.mae_modelo * 100, 1),   // error medio en pruebas con datos pasados
          error_precio_hoy_pct: redondear(q.mae_naive * 100, 1), // error si se asumiera que el precio no cambia
          mejora_pct:        redondear(q.mejora * 100, 1),
          n_pruebas:         q.n,
          entrenado_hasta:   calidad.rows[0].entrenado_hasta,
        },
        serie: serie.rows.map((r) => ({
          fecha: r.fecha,
          prom: redondear(r.precio_prom_kg, 0),
          min:  redondear(r.precio_min_kg, 0),
          max:  redondear(r.precio_max_kg, 0),
        })),
        prediccion: pred.rows.map((r) => ({
          fecha: r.fecha,
          horizonte_dias: r.horizonte_dias,
          precio: redondear(r.precio_pred_kg, 0),
          p10: redondear(r.p10_kg, 0),
          p90: redondear(r.p90_kg, 0),
          confianza: r.confianza,
          metodo: r.metodo,
        })),
      },
      { headers: CACHE_5MIN },
    );
  } catch (err) {
    return errorBD("precios/serie", err);
  }
}
