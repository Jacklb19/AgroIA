import pool from "@/lib/db";

/* Gemelo digital simple: aplica perturbaciones a la línea base predicha
   por XGBoost. No reentrena el modelo — usa elasticidades agronómicas
   típicas (lluvia, temperatura, ENSO, fertilización, suelo). */

const ELASTICIDADES = {
  lluvia_pct:     0.012,   // +1% lluvia ≈ +0.012 t/ha (rango ±30%)
  temp_delta_c:  -0.18,    // +1°C ≈ -0.18 t/ha (estrés térmico)
  enso: { "El Niño": -0.5, "La Niña": 0.3, "Neutral": 0 },
  fertilizante_pct: 0.008, // +1% dosis ≈ +0.008 t/ha (con saturación)
  aptitud:    { alta: 0.4, moderada: 0.0, marginal: -0.4, no_apta: -0.9 },
};

export async function POST(request) {
  const body = await request.json();
  const {
    muni       = "",
    cultivo    = "",
    lluvia_pct       = 0,
    temp_delta_c     = 0,
    enso             = "Neutral",
    fertilizante_pct = 0,
  } = body;

  const nombreMuni = (muni || "").split(",")[0].trim();

  let baseline = null;
  let aptitud  = null;
  try {
    const [rend, apt] = await Promise.all([
      pool.query(`
        SELECT ROUND(AVG(pr.rendimiento_predicho_t_ha)::numeric, 2) AS yhat
        FROM pred_rendimiento pr
        JOIN dim_municipio m ON m.id_municipio = pr.id_municipio
        JOIN dim_cultivo   c ON c.id_cultivo   = pr.id_cultivo
        WHERE m.nombre_municipio ILIKE $1 AND c.nombre_cultivo ILIKE $2
      `, [`%${nombreMuni}%`, `%${cultivo}%`]),
      pool.query(`
        SELECT fa.clase_aptitud
        FROM fact_aptitud_suelo fa
        JOIN dim_municipio m ON m.id_municipio = fa.id_municipio
        JOIN dim_cultivo   c ON c.id_cultivo   = fa.id_cultivo
        WHERE m.nombre_municipio ILIKE $1 AND c.nombre_cultivo ILIKE $2
        LIMIT 1
      `, [`%${nombreMuni}%`, `%${cultivo}%`]),
    ]);
    baseline = rend.rows[0]?.yhat != null ? parseFloat(rend.rows[0].yhat) : null;
    aptitud  = apt.rows[0]?.clase_aptitud || null;
  } catch (err) {
    console.error("[simular]", err.message);
  }

  const base       = baseline ?? 4.4;
  const lluviaImp  = ELASTICIDADES.lluvia_pct       * Number(lluvia_pct || 0)       * base;
  const tempImp    = ELASTICIDADES.temp_delta_c     * Number(temp_delta_c || 0);
  const ensoImp    = ELASTICIDADES.enso[enso] ?? 0;
  const fertImp    = Math.tanh(Number(fertilizante_pct || 0) / 100) * ELASTICIDADES.fertilizante_pct * 100; // saturante
  const aptImp     = aptitud ? (ELASTICIDADES.aptitud[aptitud] || 0) : 0;

  const proyectado = +(base + lluviaImp + tempImp + ensoImp + fertImp + aptImp).toFixed(2);
  const delta      = +(proyectado - base).toFixed(2);

  return Response.json({
    municipio:     nombreMuni,
    cultivo,
    baseline:      base,
    proyectado,
    delta_t_ha:    delta,
    delta_pct:     base > 0 ? +(((proyectado - base) / base) * 100).toFixed(1) : 0,
    aptitud_sipra: aptitud,
    contribuciones: [
      { factor: "Lluvia (Δ%)",        valor: +lluviaImp.toFixed(3) },
      { factor: "Temperatura (Δ°C)",  valor: +tempImp.toFixed(3)   },
      { factor: "ENSO",               valor: +ensoImp.toFixed(3)   },
      { factor: "Fertilización (Δ%)", valor: +fertImp.toFixed(3)   },
      { factor: "Aptitud SIPRA",      valor: +aptImp.toFixed(3)    },
    ],
    interpretacion: delta > 0
      ? `El escenario favorece la cosecha en ${delta.toFixed(2)} t/ha respecto a la línea base.`
      : delta < 0
        ? `El escenario reduce el rendimiento en ${Math.abs(delta).toFixed(2)} t/ha. Considera medidas de mitigación.`
        : "Escenario neutro: sin cambios significativos respecto a la línea base.",
  });
}
