import pool from "@/lib/db";
import { CACHE_5MIN, errorBD, redondear } from "@/lib/api";

export const dynamic = "force-dynamic";

/* Comparativo regional REAL: otros municipios del mismo departamento con predicción del mismo
   cultivo y año (los vecinos ya no son una lista fija). /api/comparativo?muni=Pasto&cultivo=Papa&anio=2025 */
export async function GET(request) {
  const sp = new URL(request.url).searchParams;
  const muni = (sp.get("muni") || "").split(",")[0].trim();
  const cultivo = (sp.get("cultivo") || "").trim();
  const anio = Number.parseInt(sp.get("anio"), 10);
  if (!muni || !cultivo || muni.length > 120 || cultivo.length > 120) {
    return Response.json({ error: "Parámetros 'muni' y 'cultivo' obligatorios." }, { status: 400 });
  }

  try {
    const { rows } = await pool.query(
      `WITH base AS (
         SELECT m.id_municipio, m.nombre_departamento
         FROM dim_municipio m WHERE m.nombre_municipio ILIKE $1 LIMIT 1
       ),
       anio AS (
         SELECT COALESCE($3::int, MAX(t.anio)) AS a
         FROM pred_rendimiento pr JOIN dim_tiempo t ON t.id_tiempo = pr.id_tiempo
       )
       SELECT m.nombre_municipio, pr.rendimiento_predicho_t_ha AS yhat,
              pa.nivel_riesgo AS riesgo, fp.rendimiento_t_ha AS hist, t.anio
       FROM base b
       JOIN dim_municipio m ON m.nombre_departamento = b.nombre_departamento AND m.id_municipio <> b.id_municipio
       JOIN pred_rendimiento pr ON pr.id_municipio = m.id_municipio
       JOIN dim_cultivo c ON c.id_cultivo = pr.id_cultivo AND c.nombre_cultivo ILIKE $2
       JOIN dim_tiempo t ON t.id_tiempo = pr.id_tiempo
       JOIN anio ON anio.a = t.anio
       LEFT JOIN pred_alerta_climatica pa ON pa.id_municipio = pr.id_municipio AND pa.id_tiempo = pr.id_tiempo
       LEFT JOIN fact_produccion_agricola fp
         ON fp.id_municipio = pr.id_municipio AND fp.id_cultivo = pr.id_cultivo AND fp.id_tiempo = pr.id_tiempo
       ORDER BY pr.rendimiento_predicho_t_ha DESC
       LIMIT 6`,
      [`%${muni}%`, `%${cultivo}%`, Number.isInteger(anio) ? anio : null],
    );

    return Response.json(
      {
        fromDB: true,
        vecinos: rows.map((r) => {
          const yhat = parseFloat(r.yhat);
          const hist = r.hist != null ? parseFloat(r.hist) : null;
          return {
            municipio: r.nombre_municipio,
            anio: r.anio,
            yhat: redondear(yhat, 2),
            riesgo: r.riesgo ?? null,
            vs_historico_pct: hist ? redondear(((yhat - hist) / hist) * 100, 1) : null,
          };
        }),
      },
      { headers: CACHE_5MIN },
    );
  } catch (err) {
    return errorBD("comparativo", err);
  }
}
