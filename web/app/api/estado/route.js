import pool from "@/lib/db";
import { CACHE_1MIN, errorBD } from "@/lib/api";

export const dynamic = "force-dynamic";

/* Estado operativo del sistema: frescura de cada fuente/etapa (bitácora ingest_run), últimos controles de
   calidad, modelo vigente y migraciones aplicadas. Base de la página "Datos y transparencia". No expone
   mensajes de error internos: solo si la última corrida falló. */

const seguro = (promesa) => promesa.then((r) => r.rows).catch(() => null);   // piezas opcionales (p. ej. sin migrar)

export async function GET() {
  try {
    const fuentes = await pool.query(
      `WITH ult AS (
         SELECT DISTINCT ON (fuente) fuente, status, started_at, finished_at
         FROM ingest_run WHERE fuente NOT LIKE 'alerta:%'
         ORDER BY fuente, started_at DESC
       )
       SELECT u.fuente,
              u.status                                                   AS ultimo_estado,
              u.started_at                                               AS ultima_revision,
              (SELECT MAX(r.finished_at)    FROM ingest_run r WHERE r.fuente = u.fuente AND r.status = 'ok') AS ultima_ok,
              (SELECT MAX(r.fecha_dato_max) FROM ingest_run r WHERE r.fuente = u.fuente AND r.status = 'ok') AS fecha_dato_max,
              (SELECT COUNT(*)::int FROM ingest_run r
                WHERE r.fuente = u.fuente AND r.status = 'error' AND r.started_at > NOW() - INTERVAL '24 hours') AS errores_24h
       FROM ult u ORDER BY u.fuente`,
    );

    const [calidad, modelo, migraciones] = await Promise.all([
      seguro(pool.query(
        `SELECT estado, COUNT(*)::int AS n, MAX(ejecutado_at) AS ejecutado_at
         FROM (SELECT DISTINCT ON (indicador) indicador, estado, ejecutado_at
               FROM quality_check_run ORDER BY indicador, ejecutado_at DESC) t
         GROUP BY estado`,
      )),
      seguro(pool.query(
        `SELECT nombre_modelo, fecha_entrenamiento FROM model_version
         WHERE activo ORDER BY fecha_entrenamiento DESC LIMIT 1`,
      )),
      seguro(pool.query(`SELECT COUNT(*)::int AS n, MAX(aplicada_at) AS ultima FROM schema_migrations`)),
    ]);

    const filas = fuentes.rows;
    const conErrores = filas.filter((f) => f.ultimo_estado === "error");
    const enAlerta = (calidad || []).find((c) => c.estado === "ALERTA")?.n || 0;

    return Response.json(
      {
        fromDB: true,
        estado: conErrores.length ? "con_errores" : enAlerta ? "con_alertas" : filas.length ? "ok" : "sin_datos",
        datos_de_ejemplo: filas.some((f) => f.fuente === "seed_dev"),   // base sembrada con scripts/seed_dev.py
        fuentes: filas.filter((f) => f.fuente !== "seed_dev"),
        calidad: calidad
          ? { ejecutado_at: calidad[0]?.ejecutado_at ?? null, por_estado: Object.fromEntries(calidad.map((c) => [c.estado, c.n])) }
          : null,
        modelo: modelo?.[0] ?? null,
        migraciones: migraciones?.[0] ?? null,
      },
      { headers: CACHE_1MIN },
    );
  } catch (err) {
    return errorBD("estado", err);
  }
}
