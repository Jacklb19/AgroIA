import pool from "@/lib/db";

/* Heurística agronómica simple alimentada por datos reales de la BD.
   - Ventana óptima: mes con mayor lluvia mensual histórica (ajustada por ENSO).
   - Dosis fertilizante: factor según aptitud SIPRA + déficit hídrico esperado.
   - Riesgo de plaga: intensidad de alertas activas en la zona.                */

const VENTANAS_BASE = {
  "Arroz":     { semestreA: ["abril", "mayo"],         semestreB: ["octubre", "noviembre"] },
  "Maíz":      { semestreA: ["marzo", "abril"],         semestreB: ["septiembre", "octubre"] },
  "Café":      { semestreA: ["febrero", "marzo"],       semestreB: ["agosto", "septiembre"] },
  "Caña":      { semestreA: ["enero", "febrero"],       semestreB: ["julio", "agosto"] },
  "Papa":      { semestreA: ["abril", "mayo"],          semestreB: ["octubre", "noviembre"] },
  "Plátano":   { semestreA: ["marzo", "abril"],         semestreB: ["septiembre", "octubre"] },
  "Aguacate":  { semestreA: ["febrero", "marzo"],       semestreB: ["agosto", "septiembre"] },
};

function ventanaPorCultivo(cultivo, enso) {
  const key = Object.keys(VENTANAS_BASE).find((k) => cultivo.includes(k)) || "Maíz";
  const v = VENTANAS_BASE[key];
  const ajusteEnso = enso === "El Niño" ? "Adelanta 2 semanas para evitar déficit hídrico"
                   : enso === "La Niña" ? "Atrasa 1-2 semanas y refuerza drenaje"
                   : "Mantén el calendario tradicional";
  return { cultivoBase: key, semestreA: v.semestreA, semestreB: v.semestreB, ajusteEnso };
}

function dosisFertilizante(aptitud, prob_deficit) {
  const base = aptitud === "alta" ? 250
             : aptitud === "moderada" ? 320
             : aptitud === "marginal" ? 400 : 350;
  const ajuste = (prob_deficit || 0) > 0.6 ? 30 : 0;
  return {
    nitrogenado_kg_ha: base + ajuste,
    desglose: {
      base_aptitud: base,
      ajuste_deficit: ajuste,
    },
    nota: aptitud === "no_apta"
      ? "⚠ Suelo clasificado no apto: considera rotación o un cultivo alternativo."
      : aptitud
        ? `Aptitud SIPRA: ${aptitud}.`
        : "Sin clase de aptitud SIPRA disponible — se usa dosis estándar.",
  };
}

export async function POST(request) {
  const { muni, cultivo, enso = "Neutral", lluvia = "Normal" } = await request.json();
  const nombreMuni = (muni || "").split(",")[0].trim();

  let aptitud = null, prob_deficit = null, alertasAlto = 0, rendimientoBase = null;

  try {
    const [apt, enso_q, alertas, rend] = await Promise.all([
      pool.query(`
        SELECT fa.clase_aptitud
        FROM fact_aptitud_suelo fa
        JOIN dim_municipio m ON m.id_municipio = fa.id_municipio
        JOIN dim_cultivo   c ON c.id_cultivo   = fa.id_cultivo
        WHERE m.nombre_municipio ILIKE $1 AND c.nombre_cultivo ILIKE $2
        LIMIT 1
      `, [`%${nombreMuni}%`, `%${cultivo}%`]),
      pool.query(`
        SELECT AVG(fae.probabilidad_deficit_hidrico) AS pdef
        FROM fact_alerta_enso fae
        JOIN dim_tiempo t ON t.id_tiempo = fae.id_tiempo
        WHERE t.anio >= EXTRACT(YEAR FROM CURRENT_DATE) - 2
      `),
      pool.query(`
        SELECT COUNT(*)::int AS n
        FROM pred_alerta_climatica pa
        JOIN dim_municipio m ON m.id_municipio = pa.id_municipio
        WHERE m.nombre_municipio ILIKE $1
          AND pa.activa = TRUE AND pa.nivel_riesgo = 'ALTO'
      `, [`%${nombreMuni}%`]),
      pool.query(`
        SELECT ROUND(AVG(pr.rendimiento_predicho_t_ha)::numeric, 2) AS yhat
        FROM pred_rendimiento pr
        JOIN dim_municipio m ON m.id_municipio = pr.id_municipio
        JOIN dim_cultivo   c ON c.id_cultivo   = pr.id_cultivo
        WHERE m.nombre_municipio ILIKE $1 AND c.nombre_cultivo ILIKE $2
      `, [`%${nombreMuni}%`, `%${cultivo}%`]),
    ]);
    aptitud         = apt.rows[0]?.clase_aptitud || null;
    prob_deficit    = enso_q.rows[0]?.pdef != null ? parseFloat(enso_q.rows[0].pdef) : null;
    alertasAlto     = alertas.rows[0]?.n || 0;
    rendimientoBase = rend.rows[0]?.yhat != null ? parseFloat(rend.rows[0].yhat) : null;
  } catch (err) {
    console.error("[recomendacion] DB error:", err.message);
  }

  const ventana = ventanaPorCultivo(cultivo, enso);
  const fert    = dosisFertilizante(aptitud, prob_deficit);
  const ensoAdj = enso === "El Niño" ? -0.5 : enso === "La Niña" ? 0.3 : 0;
  const lluviaAdj = lluvia === "Déficit" ? -0.4 : lluvia === "Exceso" ? -0.2 : 0;
  const proyectado = rendimientoBase != null ? +(rendimientoBase + ensoAdj + lluviaAdj).toFixed(2) : null;

  const recomendaciones = [
    {
      icono: "📅",
      titulo: "Ventana óptima de siembra",
      detalle: `Semestre A: ${ventana.semestreA.join(" / ")} · Semestre B: ${ventana.semestreB.join(" / ")}.`,
      ajuste:  ventana.ajusteEnso,
    },
    {
      icono: "🌱",
      titulo: "Dosis sugerida de fertilizante nitrogenado",
      detalle: `${fert.nitrogenado_kg_ha} kg/ha (base ${fert.desglose.base_aptitud} + ajuste ${fert.desglose.ajuste_deficit}).`,
      ajuste:  fert.nota,
    },
    {
      icono: alertasAlto > 0 ? "⚠️" : "✅",
      titulo: "Riesgo de plagas y eventos extremos",
      detalle: alertasAlto > 0
        ? `${alertasAlto} alertas de riesgo ALTO activas en ${nombreMuni}.`
        : "No hay alertas activas de riesgo alto registradas en la zona.",
      ajuste:  alertasAlto > 0
        ? "Revisa monitoreo fitosanitario y plan de contingencia hídrica antes de sembrar."
        : "Manten el monitoreo rutinario; condiciones favorables al inicio.",
    },
    {
      icono: "💧",
      titulo: "Manejo del agua según ENSO",
      detalle: enso === "El Niño"
        ? "Riego suplementario recomendado en floración y llenado de grano."
        : enso === "La Niña"
          ? "Refuerza drenaje y obras anti-encharcamiento en lotes bajos."
          : "Sin ajustes mayores: monitorea pronóstico mensual.",
      ajuste:  prob_deficit != null
        ? `Probabilidad de déficit hídrico promedio últimos 2 años: ${(prob_deficit * 100).toFixed(0)}%.`
        : "Sin histórico ENSO suficiente para una probabilidad puntual.",
    },
  ];

  return Response.json({
    municipio:           nombreMuni,
    cultivo,
    escenario:           { enso, lluvia },
    aptitud_sipra:       aptitud,
    rendimiento_base:    rendimientoBase,
    rendimiento_proyectado: proyectado,
    alertas_alto:        alertasAlto,
    recomendaciones,
  });
}
