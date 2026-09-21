import pool from "@/lib/db";
import { CACHE_5MIN, acotar, errorBD, redondear, toId } from "@/lib/precios";

import { respuestaCsv } from "@/lib/csv";

export const dynamic = "force-dynamic";

const COLUMNAS_CSV = [
  { clave: "producto", titulo: "Producto" }, { clave: "grupo", titulo: "Grupo" },
  { clave: "mercado", titulo: "Mercado" }, { clave: "departamento", titulo: "Departamento" },
  { clave: "precio_prom_kg", titulo: "Precio promedio COP/kg" }, { clave: "precio_min_kg", titulo: "Precio mínimo COP/kg" },
  { clave: "precio_max_kg", titulo: "Precio máximo COP/kg" }, { clave: "var_dia_pct", titulo: "Variación día %" },
  { clave: "var_7d_pct", titulo: "Variación 7 días %" }, { clave: "fecha", titulo: "Fecha del dato" },
];

/* Último precio mayorista por mercado × producto (vista v_precio_actual).
   Filtros: departamento (nombre exacto de /api/precios/filtros), producto (id),
   mercado (id), grupo, max_atraso (días; por defecto 30: oculta series que dejaron de reportar). */
export async function GET(request) {
  const sp = new URL(request.url).searchParams;
  const conds = [];
  const params = [];
  const add = (sql, valor) => { params.push(valor); conds.push(sql.replace("?", `$${params.length}`)); };

  add("dias_atraso <= ?", acotar(sp.get("max_atraso"), 0, 3650, 30));
  if (sp.get("departamento")) add("LOWER(departamento) = LOWER(?)", sp.get("departamento"));
  if (sp.get("grupo"))        add("LOWER(grupo) = LOWER(?)", sp.get("grupo"));
  if (toId(sp.get("producto"))) add("id_producto = ?", toId(sp.get("producto")));
  if (toId(sp.get("mercado")))  add("id_central = ?", toId(sp.get("mercado")));

  try {
    const { rows } = await pool.query(
      `SELECT id_central, mercado, ciudad, id_departamento, departamento,
              id_producto, producto, grupo,
              to_char(fecha, 'YYYY-MM-DD')          AS fecha,
              precio_prom_kg, precio_min_kg, precio_max_kg,
              precio_anterior,
              to_char(fecha_anterior, 'YYYY-MM-DD') AS fecha_anterior,
              var_dia_pct, precio_7d, var_7d_pct, dias_atraso
       FROM v_precio_actual
       WHERE ${conds.join(" AND ")}
       ORDER BY departamento, producto, mercado
       LIMIT 3000`,
      params,
    );

    /* ?formato=csv: mismos filtros, sin sparklines (descarga para Excel / análisis). */
    if (sp.get("formato") === "csv") {
      const fecha = rows.reduce((m, r) => (r.fecha > m ? r.fecha : m), "");
      return respuestaCsv(`precios-mayoristas-${fecha || "sin-datos"}`, COLUMNAS_CSV, rows.map((r) => ({
        ...r,
        precio_prom_kg: redondear(r.precio_prom_kg, 0), precio_min_kg: redondear(r.precio_min_kg, 0), precio_max_kg: redondear(r.precio_max_kg, 0),
        var_dia_pct: redondear(r.var_dia_pct, 1), var_7d_pct: redondear(r.var_7d_pct, 1),
      })));
    }

    /* Sparkline: últimos 30 días de cada serie devuelta (una sola consulta). */
    const spark = new Map();
    if (rows.length) {
      const { rows: hist } = await pool.query(
        `SELECT id_central, id_producto, array_agg(precio_prom_kg ORDER BY fecha) AS serie
         FROM fact_precio_diario
         WHERE id_producto = ANY($1::int[]) AND id_central = ANY($2::int[])
           AND fecha >= CURRENT_DATE - 30
         GROUP BY id_central, id_producto`,
        [[...new Set(rows.map((r) => r.id_producto))], [...new Set(rows.map((r) => r.id_central))]],
      );
      for (const h of hist) spark.set(`${h.id_central}:${h.id_producto}`, h.serie.map((v) => redondear(v, 0)));
    }

    return Response.json(
      {
        fromDB: true,
        total: rows.length,
        precios: rows.map((r) => ({
          ...r,
          precio_prom_kg:  redondear(r.precio_prom_kg, 0),
          precio_min_kg:   redondear(r.precio_min_kg, 0),
          precio_max_kg:   redondear(r.precio_max_kg, 0),
          precio_anterior: redondear(r.precio_anterior, 0),
          precio_7d:       redondear(r.precio_7d, 0),
          var_dia_pct:     redondear(r.var_dia_pct, 1),
          var_7d_pct:      redondear(r.var_7d_pct, 1),
          spark:           spark.get(`${r.id_central}:${r.id_producto}`) ?? [],
        })),
      },
      { headers: CACHE_5MIN },
    );
  } catch (err) {
    return errorBD("precios", err);
  }
}
