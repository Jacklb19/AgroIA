import fs from "fs/promises";
import path from "path";

/* Lee los reportes JSON emitidos por utils/extraction_quality.standardize
   y los retorna agregados. Permite al frontend mostrar la calidad real
   de cada fuente sin tener que correr Python. */

export async function GET() {
  try {
    const dir = path.resolve(process.cwd(), "..", "data", "quality_reports");
    let files;
    try {
      files = await fs.readdir(dir);
    } catch {
      return Response.json({ reportes: [], mensaje: "Aún no hay reportes de calidad. Corre el pipeline de extracción." });
    }
    const jsons = files.filter((f) => f.endsWith(".json"));
    const reportes = await Promise.all(
      jsons.map(async (f) => {
        try {
          const txt = await fs.readFile(path.join(dir, f), "utf8");
          return JSON.parse(txt);
        } catch {
          return null;
        }
      }),
    );
    const valid = reportes.filter(Boolean);
    return Response.json({
      reportes: valid.map((r) => {
        const comp = r.completitud_pct || {};
        const valores = Object.values(comp);
        const media = valores.length
          ? valores.reduce((s, v) => s + Number(v), 0) / valores.length
          : 0;
        return {
          fuente:           r.fuente,
          uri:              r.uri,
          filas:            r.filas,
          columnas:         r.columnas,
          completitud_media: +media.toFixed(1),
          duplicados:       r.duplicados_por_clave,
          extraido_at:      r.extraido_at,
          columnas_bajas:   Object.entries(comp)
            .filter(([_, v]) => Number(v) < 80)
            .map(([col, v]) => ({ col, completitud: Number(v) })),
        };
      }),
    });
  } catch (err) {
    return Response.json({ error: err.message }, { status: 500 });
  }
}
