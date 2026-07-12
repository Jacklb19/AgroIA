import pool from "@/lib/db";

export async function GET() {
  try {
    const { rows } = await pool.query(`
      SELECT DISTINCT nombre_cultivo
      FROM dim_cultivo
      ORDER BY nombre_cultivo
    `);
    const list = rows.map((r) => r.nombre_cultivo);
    return Response.json(list);
  } catch (err) {
    return Response.json(
      ["Maíz tecnificado","Arroz riego","Café arábica","Caña panelera","Plátano","Papa Diacol","Aguacate Hass"],
      { status: 200 }
    );
  }
}
