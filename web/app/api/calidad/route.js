import pool from "@/lib/db";
import { CACHE_5MIN, errorBD } from "@/lib/api";

export const dynamic = "force-dynamic";

/* Calidad de los datos, leída de la BD (el pipeline la publica en extraction_report y quality_check_run;
   antes se leían archivos del disco y no funcionaba en Vercel). */
export async function GET() {
  try {
    const [rep, ind] = await Promise.all([
      pool.query(
        `SELECT fuente, uri, filas, columnas, duplicados, completitud_pct, extraido_at
         FROM extraction_report ORDER BY fuente`,
      ),
      pool.query(
        `SELECT DISTINCT ON (indicador) indicador, descripcion, valor, estado, ejecutado_at
         FROM quality_check_run ORDER BY indicador, ejecutado_at DESC`,
      ),
    ]);

    const reportes = rep.rows.map((r) => {
      const comp = r.completitud_pct || {};
      const valores = Object.values(comp).map(Number);
      const media = valores.length ? valores.reduce((s, v) => s + v, 0) / valores.length : 0;
      return {
        fuente: r.fuente,
        uri: r.uri,
        filas: r.filas,
        columnas: r.columnas,
        completitud_media: +media.toFixed(1),
        duplicados: r.duplicados,
        extraido_at: r.extraido_at,
        columnas_bajas: Object.entries(comp)
          .filter(([, v]) => Number(v) < 80)
          .map(([col, v]) => ({ col, completitud: Number(v) })),
      };
    });

    const indicadores = ind.rows.map((r) => ({
      indicador: r.indicador,
      descripcion: r.descripcion,
      valor: r.valor,
      estado: r.estado,
      ejecutado_at: r.ejecutado_at,
    }));

    return Response.json(
      {
        fromDB: true,
        reportes,
        indicadores,
        ...(reportes.length || indicadores.length
          ? {}
          : { mensaje: "Aún no hay reportes de calidad. Corre el pipeline (python run_pipeline.py --mode core --once)." }),
      },
      { headers: CACHE_5MIN },
    );
  } catch (err) {
    return errorBD("calidad", err);
  }
}
