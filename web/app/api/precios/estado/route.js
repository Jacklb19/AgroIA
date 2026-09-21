import pool from "@/lib/db";
import { CACHE_1MIN, diasHabilesEntre, errorBD, hoyColombia } from "@/lib/precios";

export const dynamic = "force-dynamic";

/* Frescura de los datos. El cliente consulta esta ruta cada pocos minutos y solo
   recarga los precios cuando cambia `datos_actualizados_at`.
   DANE publica una vez por día hábil: "al_dia" = dato del último día hábil o del anterior. */
export async function GET() {
  try {
    const [datos, corridas] = await Promise.all([
      pool.query(`SELECT to_char(MAX(fecha), 'YYYY-MM-DD') AS fecha_dato_max FROM fact_precio_diario`),
      pool.query(
        `SELECT fuente,
                MAX(started_at)                                                     AS ultima_revision,
                MAX(finished_at) FILTER (WHERE status = 'ok')                       AS ultima_carga_ok,
                MAX(finished_at) FILTER (WHERE status = 'ok' AND filas_nuevas > 0)  AS ultimo_cambio,
                MAX(source_last_modified)                                           AS publicado_dane,
                COUNT(*) FILTER (WHERE status = 'error' AND started_at > NOW() - INTERVAL '24 hours') AS errores_24h
         FROM ingest_run
         WHERE fuente IN ('sipsa_excel', 'sipsa_soap', 'forecast_precio')   -- ingest_run también guarda etapas del pipeline y alertas
         GROUP BY fuente`,
      ),
    ]);

    const fechaDatoMax = datos.rows[0]?.fecha_dato_max ?? null;
    const porFuente = Object.fromEntries(corridas.rows.map((r) => [r.fuente, r]));
    const iso = (d) => (d ? new Date(d).toISOString() : null);

    const cambios = corridas.rows.map((r) => r.ultimo_cambio).filter(Boolean).map((d) => new Date(d).getTime());
    const revisiones = corridas.rows.map((r) => r.ultima_revision).filter(Boolean).map((d) => new Date(d).getTime());

    let estado = "sin_datos";
    let atrasoHabiles = null;
    if (fechaDatoMax) {
      atrasoHabiles = diasHabilesEntre(fechaDatoMax, hoyColombia());
      estado = atrasoHabiles <= 1 ? "al_dia" : atrasoHabiles === 2 ? "retrasado" : "desactualizado";
    }

    return Response.json(
      {
        fromDB: true,
        estado,
        fecha_dato_max: fechaDatoMax,
        atraso_dias_habiles: atrasoHabiles,
        datos_actualizados_at: cambios.length ? new Date(Math.max(...cambios)).toISOString() : null,
        ultima_revision_at: revisiones.length ? new Date(Math.max(...revisiones)).toISOString() : null,
        publicado_dane_at: iso(porFuente.sipsa_excel?.publicado_dane),
        errores_24h: corridas.rows.reduce((s, r) => s + Number(r.errores_24h || 0), 0),
        fuente: "DANE - SIPSA",
      },
      { headers: CACHE_1MIN },
    );
  } catch (err) {
    return errorBD("precios/estado", err);
  }
}
