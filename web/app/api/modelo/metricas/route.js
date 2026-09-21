import pool from "@/lib/db";
import { CACHE_5MIN, errorBD, redondear } from "@/lib/api";

export const dynamic = "force-dynamic";

const num = (v, d = 3) => (v == null || Number.isNaN(Number(v)) ? null : redondear(v, d));

/* Métricas REALES de los modelos activos (tabla model_version). Sustituye a las cifras escritas a mano.
   Cada modelo es null si todavía no se ha entrenado. */
export async function GET() {
  try {
    const { rows } = await pool.query(`
      SELECT DISTINCT ON (nombre_modelo) nombre_modelo, id_version,
             to_char(fecha_entrenamiento, 'YYYY-MM-DD') AS fecha, metricas_json AS m
      FROM model_version
      WHERE activo
      ORDER BY nombre_modelo, id_version DESC
    `);
    const json = (r) => (r.m && typeof r.m === "string" ? JSON.parse(r.m) : r.m) || {};
    const buscar = (patron) => rows.find((r) => patron.test(r.nombre_modelo));

    const rend = buscar(/rendimiento/);
    const alerta = buscar(/alerta/);
    const precio = buscar(/precio/);

    return Response.json(
      {
        fromDB: true,
        rendimiento: rend && (() => {
          const m = json(rend);
          return {
            modelo: rend.nombre_modelo, entrenado: rend.fecha,
            r2: num(m.r2), mae_t_ha: num(m.mae), rmse_t_ha: num(m.rmse),
            n_train: m.n_train ?? null, n_test: m.n_test ?? null,
            anio_corte: m.split_year ?? null, n_variables: m.n_features ?? null,
            evaluacion: m.evaluacion ?? null,
            linea_base: m.linea_base
              ? { descripcion: m.linea_base.descripcion, mae_t_ha: num(m.linea_base.mae), rmse_t_ha: num(m.linea_base.rmse), r2: num(m.linea_base.r2) }
              : null,
            mejora_mae_vs_base_pct: num(m.mejora_mae_vs_base_pct, 1),
            cobertura_p10_p90: m.cobertura_p10_p90 != null ? num(m.cobertura_p10_p90 * 100, 0) : null,
            cv_mae_t_ha: num(m.cv_mae),
            pruebas_optuna: m.optuna_trials ?? null,
            anios_con_datos: m.anios_con_datos ?? null,
          };
        })(),
        alerta: alerta && (() => {
          const m = json(alerta);
          return { modelo: alerta.nombre_modelo, entrenado: alerta.fecha, f1_ponderado: num(m.f1_weighted), n_test: m.n_test ?? null, nota: m.note ?? null };
        })(),
        precios: precio && (() => {
          const m = json(precio);
          const bt = m.backtest || {};
          return {
            modelo: precio.nombre_modelo, entrenado: precio.fecha,
            error_modelo_pct: bt.mae_log_modelo != null ? num(bt.mae_log_modelo * 100, 1) : null,
            error_precio_hoy_pct: bt.mae_log_naive != null ? num(bt.mae_log_naive * 100, 1) : null,
            mejora_pct: bt.mejora_global != null ? num(bt.mejora_global * 100, 1) : null,
            horizonte_max_dias_habiles: m.horizonte_max ?? null,
          };
        })(),
      },
      { headers: CACHE_5MIN },
    );
  } catch (err) {
    return errorBD("modelo/metricas", err);
  }
}
