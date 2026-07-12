import fs from "fs/promises";
import path from "path";

export async function GET() {
  try {
    const csvPath = path.resolve(process.cwd(), "..", "data", "quality_reports", "anova_resumen.csv");
    const txt = await fs.readFile(csvPath, "utf-8");

    // Strip BOM if present
    const clean = txt.replace(/^﻿/, "").trim();
    const lines = clean.split("\n");
    const headers = lines[0].split(",").map((h) => h.trim());

    const pruebas = lines.slice(1)
      .filter(Boolean)
      .map((line) => {
        const vals = line.split(",");
        return Object.fromEntries(headers.map((h, i) => [h, (vals[i] ?? "").trim()]));
      });

    return Response.json({ pruebas });
  } catch {
    return Response.json({ pruebas: [] });
  }
}
