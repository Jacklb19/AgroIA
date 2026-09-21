import pool from "@/lib/db";
import { CACHE_5MIN, errorBD } from "@/lib/precios";

export const dynamic = "force-dynamic";

/* Opciones de los filtros: departamentos, mercados y productos con dato reciente. */
export async function GET() {
  try {
    const { rows } = await pool.query(
      `SELECT id_central, mercado, ciudad, id_departamento, departamento,
              id_producto, producto, grupo
       FROM v_precio_actual
       WHERE dias_atraso <= 30`,
    );

    const departamentos = new Map();
    const mercados = new Map();
    const productos = new Map();
    for (const r of rows) {
      if (r.departamento && !departamentos.has(r.departamento)) {
        departamentos.set(r.departamento, { id: r.id_departamento, nombre: r.departamento });
      }
      if (!mercados.has(r.id_central)) {
        mercados.set(r.id_central, {
          id: r.id_central, nombre: r.mercado, ciudad: r.ciudad,
          departamento: r.departamento, id_departamento: r.id_departamento,
        });
      }
      if (!productos.has(r.id_producto)) {
        productos.set(r.id_producto, { id: r.id_producto, nombre: r.producto, grupo: r.grupo });
      }
    }
    const porNombre = (a, b) => a.nombre.localeCompare(b.nombre, "es");

    return Response.json(
      {
        fromDB: true,
        departamentos: [...departamentos.values()].sort(porNombre),
        mercados: [...mercados.values()].sort(porNombre),
        productos: [...productos.values()].sort(porNombre),
      },
      { headers: CACHE_5MIN },
    );
  } catch (err) {
    return errorBD("precios/filtros", err);
  }
}
