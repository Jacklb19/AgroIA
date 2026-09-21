import pool from "@/lib/db";
import { CACHE_5MIN, errorBD } from "@/lib/precios";

export const dynamic = "force-dynamic";

/* Informe diario generado por run_prices.py (tabla informe_precio_diario).
   /api/precios/informe            -> el más reciente
   /api/precios/informe?fecha=YYYY-MM-DD */
export async function GET(request) {
  const fecha = new URL(request.url).searchParams.get("fecha");
  if (fecha && !/^\d{4}-\d{2}-\d{2}$/.test(fecha)) {
    return Response.json({ error: "Formato de fecha inválido. Usa YYYY-MM-DD." }, { status: 400 });
  }

  try {
    const [informe, fechas] = await Promise.all([
      pool.query(
        `SELECT to_char(fecha, 'YYYY-MM-DD') AS fecha, payload, generado_at
         FROM informe_precio_diario
         WHERE $1::date IS NULL OR fecha = $1::date
         ORDER BY fecha DESC LIMIT 1`,
        [fecha || null],
      ),
      pool.query(`SELECT to_char(fecha, 'YYYY-MM-DD') AS fecha FROM informe_precio_diario ORDER BY fecha DESC LIMIT 30`),
    ]);

    if (!informe.rows.length) {
      return Response.json({ fromDB: true, informe: null, fechas: fechas.rows.map((r) => r.fecha) }, { status: 404 });
    }
    const fila = informe.rows[0];
    return Response.json(
      {
        fromDB: true,
        fecha: fila.fecha,
        generado_at: new Date(fila.generado_at).toISOString(),
        informe: fila.payload,
        fechas: fechas.rows.map((r) => r.fecha),
      },
      { headers: CACHE_5MIN },
    );
  } catch (err) {
    return errorBD("precios/informe", err);
  }
}
