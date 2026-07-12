import pool from "@/lib/db";

export async function GET() {
  try {
    const { rows } = await pool.query("SELECT NOW() AS hora, current_database() AS bd");
    return Response.json({ ok: true, ...rows[0] });
  } catch (err) {
    return Response.json({
      ok:     false,
      error:  err.message,
      code:   err.code,
      detail: err.detail,
    }, { status: 500 });
  }
}
