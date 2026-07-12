import pool from "@/lib/db";

export async function GET() {
  try {
    const { rows } = await pool.query(`
      SELECT DISTINCT
        m.nombre_municipio || ', ' || m.nombre_departamento AS municipio
      FROM dim_municipio m
      ORDER BY 1
    `);
    const list = rows.map((r) => r.municipio);
    return Response.json(list);
  } catch (err) {
    return Response.json(
      ["Ibagué, Tolima","Espinal, Tolima","Villavicencio, Meta","Pasto, Nariño","Santa Marta, Magdalena","Manizales, Caldas","Montería, Córdoba"],
      { status: 200 }
    );
  }
}
