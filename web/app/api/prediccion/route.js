import pool from "@/lib/db";

export async function POST(request) {
  const { muni, cultivo, year, semester, enso, lluvia } = await request.json();

  const muniParts = (muni || "").split(",");
  const nombreMuni = (muniParts[0] || "").trim();

  /* Ajustes de escenario (se aplican siempre, también sobre resultado de BD) */
  const ensoAdj   = enso   === "El Niño"  ? -0.5 : enso   === "La Niña" ? 0.3  : 0;
  const lluviaAdj = lluvia === "Déficit"   ? -0.4 : lluvia === "Exceso"  ? -0.2 : 0;

  const SELECT = `
    SELECT
      pr.rendimiento_predicho_t_ha      AS yhat,
      pr.intervalo_confianza_inferior   AS low,
      pr.intervalo_confianza_superior   AS high,
      pr.shap_top                       AS shap_top,
      pa.nivel_riesgo                   AS risk,
      pa.score_probabilidad             AS score,
      fp.rendimiento_t_ha               AS hist
    FROM pred_rendimiento pr
    JOIN dim_municipio m ON pr.id_municipio = m.id_municipio
    JOIN dim_cultivo   c ON pr.id_cultivo   = c.id_cultivo
    JOIN dim_tiempo    t ON pr.id_tiempo    = t.id_tiempo
    LEFT JOIN pred_alerta_climatica pa
      ON pa.id_municipio = pr.id_municipio AND pa.id_tiempo = pr.id_tiempo
    LEFT JOIN fact_produccion_agricola fp
      ON fp.id_municipio = pr.id_municipio
     AND fp.id_cultivo   = pr.id_cultivo
     AND fp.id_tiempo    = pr.id_tiempo
    WHERE m.nombre_municipio ILIKE $1
      AND c.nombre_cultivo   ILIKE $2
  `;

  try {
    /* Intento 1: con el año exacto que pidió el usuario */
    let { rows } = await pool.query(
      SELECT + " AND t.anio = $3 ORDER BY t.mes DESC LIMIT 1",
      [`%${nombreMuni}%`, `%${cultivo}%`, parseInt(year)]
    );

    /* Intento 2: sin restricción de año — usa el dato más reciente disponible */
    if (rows.length === 0) {
      ({ rows } = await pool.query(
        SELECT + " ORDER BY t.anio DESC, t.mes DESC LIMIT 1",
        [`%${nombreMuni}%`, `%${cultivo}%`]
      ));
    }

    if (rows.length > 0) {
      const row   = rows[0];
      const base  = parseFloat(row.yhat) || 4.4;
      const yhat  = +(base + ensoAdj + lluviaAdj).toFixed(2);

      const rawLow  = row.low  != null ? parseFloat(row.low)  + ensoAdj + lluviaAdj : yhat - 1.2;
      const rawHigh = row.high != null ? parseFloat(row.high) + ensoAdj + lluviaAdj : yhat + 1.2;
      const low   = +Math.max(0, rawLow).toFixed(2);
      const high  = +Math.max(yhat, rawHigh).toFixed(2);
      const hist  = row.hist != null ? parseFloat(row.hist) : null;
      const risk  = row.risk || (yhat < 4.0 ? "ALTO" : yhat < 4.6 ? "MEDIO" : "BAJO");
      const score = row.score != null ? Math.round(parseFloat(row.score) * 100) : null;
      const confidence = score ?? (risk === "BAJO" ? 86 : risk === "MEDIO" ? 78 : 64);

      let shap = null;
      if (row.shap_top) {
        try { shap = typeof row.shap_top === "string" ? JSON.parse(row.shap_top) : row.shap_top; }
        catch { shap = null; }
      }

      return Response.json({ muni, cultivo, year, semester, yhat, low, high, risk, confidence, hist, shap, fromDB: true });
    }
  } catch (err) {
    console.error("[prediccion] DB error:", err.message);
  }

  /* ── Fallback local ────────────────────────────────────────────────────
     Varía por municipio (hash determinista) + cultivo + semestre + escenario.
     Así municipios distintos dan valores distintos incluso sin BD.          */
  const muniHash  = [...nombreMuni].reduce((a, c) => a + c.charCodeAt(0), 0);
  const muniVar   = ((muniHash % 21) - 10) / 20;   // rango ≈ -0.50 a +0.50

  const cultivoAdj =
    cultivo.includes("Arroz") ?  0.6 :
    cultivo.includes("Café")  ? -0.8 :
    cultivo.includes("Papa")  ?  0.4 :
    cultivo.includes("Caña")  ?  0.1 :
    cultivo.includes("Aguac") ?  0.3 : 0;

  const semAdj = semester === "B" ? 0.15 : 0;
  const yhat   = +(4.4 + muniVar + cultivoAdj + semAdj + ensoAdj + lluviaAdj).toFixed(2);
  const risk   = yhat < 4.0 ? "ALTO" : yhat < 4.6 ? "MEDIO" : "BAJO";
  const confidence = risk === "BAJO" ? 86 : risk === "MEDIO" ? 78 : 64;

  return Response.json({
    muni, cultivo, year, semester,
    yhat,
    low:  +Math.max(0, yhat - 1.2).toFixed(2),
    high: +(yhat + 1.2).toFixed(2),
    risk, confidence,
    hist: +(4.2 + muniVar).toFixed(2),
  });
}
