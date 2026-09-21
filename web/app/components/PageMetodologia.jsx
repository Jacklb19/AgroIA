"use client";
import { useEffect, useState } from "react";
import { Icon } from "./icons";
import { useApi } from "@/lib/useApi";

/* ─── Metadata editorial de cada prueba ANOVA ─────────────────────────────── */
const ANOVA_TESTS = [
  {
    id: 1,
    imagen: "anova_precipitacion_enso.png",
    titulo: "Lluvia y fenómeno El Niño / La Niña",
    pregunta: "¿Llueve diferente según el estado del clima global?",
    explicacion:
      "Comparamos la lluvia mensual promedio de Colombia durante El Niño, La Niña y meses Neutros (un dato por mes calendario). Existe una diferencia, pero es pequeña: la fase ENSO explica solo una parte reducida de la variación de un mes a otro, y únicamente El Niño frente a Neutro se distingue con claridad. Que una diferencia sea estadísticamente significativa no significa que sea grande: mira el tamaño del efecto.",
    fuente: "IDEAM · promedio mensual nacional",
    color: "#1e4d7b",
    colorLight: "#e8f0f7",
  },
  {
    id: 3,
    imagen: "anova_precipitacion_trimestre.png",
    titulo: "Lluvias según la época del año",
    pregunta: "¿Hay épocas con más lluvia que otras en Colombia?",
    explicacion:
      "Colombia tiene un régimen de lluvias marcado por la época del año. Comparamos la lluvia mensual promedio por trimestre: el primer trimestre (enero–marzo) es claramente más seco que los demás y el efecto es grande. Conocer este patrón ayuda a programar la siembra y la cosecha.",
    fuente: "IDEAM · promedio mensual nacional",
    color: "#155436",
    colorLight: "#ecf7f0",
  },
  {
    id: 4,
    imagen: "anova_precipitacion_nasa_municipios.png",
    titulo: "Lluvia en tres ciudades colombianas (datos NASA)",
    pregunta: "¿Llueve igual en Ibagué, Pasto y Villavicencio?",
    explicacion:
      "Con datos del satélite de la NASA (MERRA-2, distinto de las estaciones del IDEAM) comparamos el promedio mensual de lluvia en tres ciudades durante 2024. Con solo 12 meses por ciudad, la muestra es pequeña: hay una diferencia global, pero ningún par de ciudades se distingue de forma concluyente después de corregir por comparaciones múltiples.",
    fuente: "NASA POWER MERRA-2 · 12 meses de 2024 por ciudad",
    color: "#7B2D8B",
    colorLight: "#f5eef8",
  },
];

function SigBadge({ sig }) {
  const ok = sig === "***" || sig === "**" || sig === "*";
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      fontSize: 11, fontWeight: 700, padding: "3px 10px",
      borderRadius: 20,
      background: ok ? "#d6ecdf" : "#f3f4f6",
      color: ok ? "#155436" : "#6b7280",
      letterSpacing: 0.2,
    }}>
      {ok ? "✓ Diferencias reales confirmadas" : "Sin diferencias significativas"}
    </span>
  );
}

function AnovaCard({ test, datos }) {
  const [open, setOpen] = useState(false);
  const row = datos.find((r) => r["Prueba"]?.includes(test.id === 1 ? "ENSO" : test.id === 3 ? "Trimestre" : "NASA"));

  return (
    <div style={{
      border: "1px solid var(--ink-200)",
      borderRadius: 12,
      background: "white",
      overflow: "hidden",
      display: "flex",
      flexDirection: "column",
      boxShadow: "var(--shadow-sm)",
    }}>
      {/* Header */}
      <div style={{ padding: "14px 18px", background: test.colorLight, borderBottom: "1px solid var(--ink-200)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <span style={{
            width: 22, height: 22, borderRadius: "50%",
            background: test.color, color: "white",
            fontSize: 11, fontWeight: 700,
            display: "inline-flex", alignItems: "center", justifyContent: "center",
            flexShrink: 0,
          }}>{test.id}</span>
          <span style={{ fontSize: 10, fontWeight: 600, color: test.color, textTransform: "uppercase", letterSpacing: 0.8 }}>
            Prueba {test.id}
          </span>
        </div>
        <h4 style={{ fontSize: 15, fontWeight: 700, color: "var(--ink-900)", margin: 0, lineHeight: 1.25 }}>
          {test.titulo}
        </h4>
        <p style={{ fontSize: 12.5, color: "var(--ink-600)", margin: "4px 0 0", fontStyle: "italic" }}>
          {test.pregunta}
        </p>
      </div>

      {/* Boxplot image */}
      <div style={{ background: "#fafafa", padding: "12px 18px", borderBottom: "1px solid var(--ink-100)", textAlign: "center" }}>
        <img
          src={`/images/${test.imagen}`}
          alt={`Boxplot: ${test.titulo}`}
          style={{ maxWidth: "100%", height: "auto", borderRadius: 8 }}
          loading="lazy"
          onError={(e) => { e.target.style.display = "none"; }}
        />
      </div>

      {/* Explicación */}
      <div style={{ padding: "14px 18px", flex: 1, display: "flex", flexDirection: "column", gap: 10 }}>
        {row && <SigBadge sig={row["Sig."]} />}

        <p style={{ fontSize: 13, color: "var(--ink-700)", lineHeight: 1.6, margin: 0 }}>
          {test.explicacion}
        </p>

        {/* Fuente */}
        <div style={{ fontSize: 11, color: "var(--ink-500)", borderTop: "1px solid var(--ink-100)", paddingTop: 8 }}>
          Datos: {test.fuente}
        </div>

        {/* Toggle estadísticas técnicas */}
        {row && (
          <>
            <button
              onClick={() => setOpen(!open)}
              style={{
                background: "none", border: "1px solid var(--ink-200)",
                borderRadius: 6, padding: "5px 10px",
                fontSize: 11.5, color: "var(--ink-500)", cursor: "pointer",
                alignSelf: "flex-start", display: "flex", alignItems: "center", gap: 4,
              }}
            >
              {open ? "▲" : "▼"} {open ? "Ocultar" : "Ver"} estadísticas técnicas
            </button>
            {open && (
              <div style={{
                background: "var(--ink-50)", borderRadius: 8,
                padding: "10px 14px", fontSize: 12,
                fontFamily: "var(--font-mono)",
                display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px 16px",
                color: "var(--ink-700)",
              }}>
                <span>F de Welch</span><span style={{ color: "var(--ink-900)", fontWeight: 600 }}>{parseFloat(row["F"]).toFixed(3)}</span>
                <span>Tamaño del efecto (η²)</span><span style={{ fontWeight: 700 }}>{row["eta2"] ?? "—"} · {row["Efecto"] ?? "n/d"}</span>
                <span>Kruskal-Wallis p</span><span>{row["Kruskal p"] != null ? (parseFloat(row["Kruskal p"]) < 0.0001 ? "< 0.0001" : row["Kruskal p"]) : "—"}</span>
                <span>p-valor</span><span style={{ color: parseFloat(row["p-valor"]) < 0.05 ? "#155436" : "var(--ink-600)", fontWeight: 600 }}>{parseFloat(row["p-valor"]) < 0.0001 ? "< 0.0001" : row["p-valor"]}</span>
                <span>Grupos</span><span>{row["Grupos"]}</span>
                <span>Unidades (meses)</span><span>{parseInt(row["N total"]).toLocaleString("es-CO")}</span>
                <span>Levene p</span><span>{row["Levene p"]}</span>
                <span>Significancia</span><span style={{ fontWeight: 700 }}>{row["Sig."]}</span>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function SectionAnova() {
  const [datos, setDatos] = useState([]);
  useEffect(() => {
    fetch("/anova_data.json").then((r) => r.json()).then((d) => setDatos(d.pruebas || [])).catch(() => {});
  }, []);

  return (
    <div className="card" style={{ marginTop: 28 }}>
      <div className="card-head">
        <div>
          <h3>Análisis estadístico — comparación de grupos</h3>
          <div className="panel-sub">¿Qué confirman los datos con evidencia estadística?</div>
        </div>
        <span className="src-badge">validate/anova_tests.py</span>
      </div>
      <div className="card-body">
        {/* Explicación general */}
        <div style={{
          background: "var(--blue-50)", border: "1px solid var(--blue-100)",
          borderRadius: 10, padding: "14px 18px", marginBottom: 24,
          display: "flex", gap: 12, alignItems: "flex-start",
        }}>
          <span style={{ fontSize: 22, flexShrink: 0 }}>📊</span>
          <div>
            <p style={{ margin: "0 0 6px", fontSize: 13.5, fontWeight: 600, color: "var(--blue-700)" }}>
              ¿Qué es un análisis ANOVA?
            </p>
            <p style={{ margin: 0, fontSize: 13, color: "var(--ink-700)", lineHeight: 1.65 }}>
              ANOVA compara grupos para ver si las diferencias entre ellos pueden ser producto del azar. Por ejemplo: si llueve más durante La Niña que en El Niño. Dos advertencias importantes: (1) comparamos <strong>un dato por mes</strong>, no miles de lecturas de estaciones del mismo mes, porque esas lecturas no son independientes; y (2) un valor p pequeño solo dice que hay <em>alguna</em> diferencia, no que sea grande: por eso se reporta el <strong>tamaño del efecto (η²)</strong> — la fracción de la variación que explica el factor.
            </p>
          </div>
        </div>

        {/* Grid de pruebas */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(min(340px, 100%), 1fr))",
          gap: 20,
        }}>
          {ANOVA_TESTS.map((test) => (
            <AnovaCard key={test.id} test={test} datos={datos} />
          ))}
        </div>

        {/* Nota protocolo */}
        <div style={{ fontSize: 11.5, color: "var(--ink-500)", marginTop: 18, lineHeight: 1.6 }}>
          <strong>Protocolo estadístico:</strong> cada prueba agrega a unidades independientes y ejecuta (1) Levene (por la mediana) para las varianzas, (2) ANOVA de Welch, que no exige varianzas iguales, (3) Kruskal-Wallis, que no exige normalidad, (4) tamaño del efecto η² y (5) comparaciones por pares con Mann-Whitney y corrección de Holm. Se eliminó la prueba de precios de insumos por tipo: comparaba unidades distintas. Código en <code>validate/anova_robusto.py</code>.
        </div>
      </div>
    </div>
  );
}

function fmtFilas(n) {
  if (n == null) return "—";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, "") + "M";
  if (n >= 1_000)     return (n / 1_000).toFixed(1).replace(/\.0$/, "") + "k";
  return n.toLocaleString("es-CO");
}

export default function PageMetodologia() {
  const [fuentes, setFuentes] = useState([]);
  const [calidad, setCalidad] = useState([]);
  const modeloApi = useApi("/api/modelo/metricas");
  const modeloR = modeloApi.data?.rendimiento ?? null;
  useEffect(() => {
    fetch("/api/catalogo").then((r) => r.json()).then((d) => setFuentes(Array.isArray(d) ? d : [])).catch(() => setFuentes([]));
    fetch("/api/calidad").then((r) => r.json()).then((d) => setCalidad(d.reportes || [])).catch(() => setCalidad([]));
  }, []);

  return (
    <section className="section">
      <div className="container">
        <div className="section-head">
          <span className="eyebrow blue">Metodología</span>
          <h2>Pipeline reproducible y auditable</h2>
          <p>Cada paso del modelado está documentado, versionado y validado contra datos retenidos. Métricas calculadas en tiempo de entrenamiento y persistidas en <code>model_version</code>.</p>
        </div>

        <div className="card" style={{ marginBottom: 28 }}>
          <div className="card-head">
            <div>
              <h3>Alineación con la Hoja de Ruta Sectorial Agropecuaria</h3>
              <div className="panel-sub">Datos abiertos estratégicos · Plan Nacional de Datos Abiertos (MinTIC)</div>
            </div>
            <span className="src-badge">datos.gov.co</span>
          </div>
          <div className="card-body">
            <p style={{ marginBottom: 12, fontSize: 13, color: "var(--gray-700)" }}>
              AgroIA prioriza la integración de los conjuntos definidos como <strong>estratégicos</strong> en la Hoja de Ruta Sectorial Agropecuaria y en el Plan Nacional de Datos Abiertos. Cada fuente entra al pipeline ETL con su URI Socrata o GeoServer y queda trazable en <code>config/settings.py</code>.
            </p>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 10 }}>
              {(fuentes.length > 0 ? fuentes : []).map((f) => (
                <div key={f.id} style={{ padding: "10px 12px", border: "1px solid var(--gray-200)", borderRadius: 8, background: "white", display: "flex", flexDirection: "column", gap: 4 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                    <a href={f.uri} target="_blank" rel="noopener noreferrer" style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--blue-700)", textDecoration: "none" }}>
                      {f.id} ↗
                    </a>
                    {f.estrategico && (
                      <span style={{ fontSize: 10, fontWeight: 600, padding: "2px 6px", borderRadius: 4, background: "#1a7a4a", color: "white", textTransform: "uppercase", letterSpacing: 0.4 }}>
                        Estratégico
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{f.titulo}</div>
                  <div style={{ fontSize: 11, color: "var(--gray-600)", display: "flex", justifyContent: "space-between" }}>
                    <span>{f.entidad}</span>
                    {f.tabla && <code style={{ fontSize: 10 }}>{f.tabla}</code>}
                  </div>
                  <div style={{ fontSize: 11, color: f.filas != null ? "#1a7a4a" : "var(--gray-500)" }}>
                    {f.filas != null ? `${fmtFilas(f.filas)} filas en BD` : "Sin datos cargados"}
                  </div>
                </div>
              ))}
              {fuentes.length === 0 && (
                <div style={{ gridColumn: "1 / -1", fontSize: 12, color: "var(--gray-500)", textAlign: "center", padding: 12 }}>
                  Cargando catálogo de fuentes…
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="method-grid">
          <div className="method-card">
            <div className="icon-wrap"><Icon.database /></div>
            <h3>Fuentes de datos abiertos</h3>
            <ul>
              <li>DANE — evaluaciones agropecuarias municipales (A04/A05)</li>
              <li>IDEAM — series climáticas (precipitación, temperatura)</li>
              <li>UPRA — SIPRA aptitud agrícola por suelo</li>
              <li>DANE — SIPSA precios mayoristas + IPIA insumos</li>
              <li>NOAA — índice ENSO mensual</li>
            </ul>
          </div>
          <div className="method-card">
            <div className="icon-wrap"><Icon.brush /></div>
            <h3>Flujo ETL</h3>
            <ul>
              <li>Extracción Socrata + GeoServer + scraping institucional</li>
              <li>Armonización municipio · cultivo · ciclo (DIVIPOLA)</li>
              <li>Filtros de rango y deduplicación por clave natural</li>
              <li>Feature store calculado desde el star schema en cada entrenamiento</li>
            </ul>
          </div>
          <div className="method-card">
            <div className="icon-wrap"><Icon.layers /></div>
            <h3>Star schema</h3>
            <ul>
              <li>6 dimensiones · 7 hechos · 2 tablas de predicción</li>
              <li>fact_produccion_agricola · fact_clima_mensual</li>
              <li>fact_precios_mayoristas · fact_precios_insumos</li>
              <li>fact_alerta_enso · fact_aptitud_suelo · fact_censo</li>
            </ul>
          </div>
          <div className="method-card green">
            <div className="icon-wrap"><Icon.tree /></div>
            <h3>Modelo principal</h3>
            <ul>
              <li>XGBoost que aprende la <strong>desviación respecto al promedio histórico</strong> del municipio × cultivo</li>
              <li>Rasgos: clima anual + rezagos 1 y 3 años + ENSO (ONI) + precios SIPSA + índice de insumos. Los datos faltantes se dejan vacíos (no se rellenan con 0)</li>
              <li>Ajuste bayesiano (Optuna) con validación temporal por año</li>
              <li>Aptitud de suelo (UPRA) fuera del modelo por ahora: su servicio dejó de estar disponible</li>
            </ul>
          </div>
          <div className="method-card amber">
            <div className="icon-wrap"><Icon.ruler /></div>
            <h3>Validación y métricas</h3>
            <ul>
              <li>Métricas reales en <code>model_version.metricas_json</code></li>
              <li>El último año con datos se reserva como <strong>año de prueba</strong>: no se usa para entrenar ni para ajustar</li>
              <li>Se compara siempre con una línea base (promedio histórico)</li>
              <li>Rango probable p10–p90 calibrado con los errores reales de validación; se reporta su cobertura</li>
              <li>Solo se publican predicciones fuera de muestra</li>
            </ul>
          </div>
          <div className="method-card red">
            <div className="icon-wrap"><Icon.shield /></div>
            <h3>Explicabilidad e interpretabilidad</h3>
            <ul>
              <li>SHAP TreeExplainer · top-10 importancia global</li>
              <li>Top-3 factores con signo por predicción</li>
              <li>Persistido en <code>pred_rendimiento.shap_top</code> (JSONB)</li>
              <li>Visualizado en panel "Por qué esta predicción"</li>
            </ul>
          </div>
        </div>

        <div className="metrics-table-wrap">
          <div className="head">
            <div>
              <h3>Modelo vs. línea base</h3>
              <p>Evaluación fuera de muestra sobre el último año con datos.</p>
            </div>
            <span className="src-badge">model_version · activo</span>
          </div>
          <table className="metrics-table">
            <thead>
              <tr><th>Modelo</th><th colSpan={3}>Métricas</th><th>Notas</th></tr>
            </thead>
            <tbody>
              {modeloR ? (
                <>
                  <tr>
                    <td><strong>XGBoost</strong> <span className="winner-cell">activo</span></td>
                    <td className="num">MAE {modeloR.mae_t_ha} t/ha</td>
                    <td className="num">RMSE {modeloR.rmse_t_ha} t/ha</td>
                    <td className="num">R² {modeloR.r2}</td>
                    <td style={{ fontSize: 11 }}>Año de prueba {modeloR.anio_corte} · {modeloR.n_test?.toLocaleString("es-CO")} predicciones · {modeloR.pruebas_optuna} pruebas de ajuste</td>
                  </tr>
                  {modeloR.linea_base && (
                    <tr>
                      <td>Línea base: {modeloR.linea_base.descripcion}</td>
                      <td className="num">MAE {modeloR.linea_base.mae_t_ha} t/ha</td>
                      <td className="num">RMSE {modeloR.linea_base.rmse_t_ha} t/ha</td>
                      <td className="num">R² {modeloR.linea_base.r2}</td>
                      <td style={{ fontSize: 11 }}>Sin modelo: repite lo que pasó en años anteriores</td>
                    </tr>
                  )}
                  <tr>
                    <td colSpan={5} style={{ fontSize: 12 }}>
                      El modelo {modeloR.mejora_mae_vs_base_pct >= 0 ? "reduce" : "aumenta"} el error absoluto en <strong>{Math.abs(modeloR.mejora_mae_vs_base_pct)} %</strong> respecto a la línea base.
                      {modeloR.cobertura_p10_p90 != null && <> El rango p10–p90 contiene el valor real en el <strong>{modeloR.cobertura_p10_p90} %</strong> de los casos (esperado: 80 %).</>}
                      {" "}El R² es alto porque los cultivos tienen rendimientos muy distintos entre sí; por eso la comparación relevante es el MAE frente a la línea base.
                    </td>
                  </tr>
                </>
              ) : (
                <tr><td colSpan={5} style={{ fontSize: 12 }}>Todavía no hay un modelo de rendimiento entrenado y registrado.</td></tr>
              )}
            </tbody>
          </table>
          <div style={{ fontSize: 12, color: "var(--gray-600)", marginTop: 10 }}>
            ℹ Las métricas exactas se calculan en cada corrida de <code>models/train_rendimiento.py</code> y se persisten en la tabla <code>model_version</code>. Para ver el último valor activo: <code>SELECT metricas_json FROM model_version WHERE activo = TRUE</code>.
          </div>
          <div style={{ fontSize: 12, color: "var(--gray-600)", marginTop: 8 }}>
            🛠 API pública documentada en <a href="/api/openapi" target="_blank" rel="noopener noreferrer"><code>/api/openapi</code></a> (OpenAPI 3.1).
          </div>
        </div>

        {/* ── Auditoría de calidad de fuentes ─────────────────────── */}
        {calidad.length > 0 && (
          <div className="card" style={{ marginTop: 28 }}>
            <div className="card-head">
              <div>
                <h3>Auditoría de calidad por fuente</h3>
                <div className="panel-sub">Reportes generados durante la extracción · `data/quality_reports/`</div>
              </div>
              <span className="src-badge">utils/extraction_quality</span>
            </div>
            <div className="card-body" style={{ overflowX: "auto" }}>
              <table className="metrics-table" style={{ minWidth: 720 }}>
                <thead>
                  <tr>
                    <th>Fuente</th>
                    <th>Filas</th>
                    <th>Columnas</th>
                    <th>Completitud media</th>
                    <th>Duplicados</th>
                    <th>Última extracción</th>
                  </tr>
                </thead>
                <tbody>
                  {calidad.map((c) => {
                    const cls = c.completitud_media >= 95 ? "best" : c.completitud_media >= 80 ? "mid" : "worst";
                    return (
                      <tr key={c.fuente}>
                        <td><code style={{ fontSize: 11 }}>{c.fuente}</code></td>
                        <td className="num">{c.filas?.toLocaleString("es-CO")}</td>
                        <td className="num">{c.columnas}</td>
                        <td className={`num ${cls}`}>{c.completitud_media}%</td>
                        <td className={`num ${c.duplicados > 0 ? "worst" : "best"}`}>{c.duplicados}</td>
                        <td style={{ fontSize: 11, fontFamily: "var(--font-mono)" }}>{c.extraido_at}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <div style={{ fontSize: 11, color: "var(--gray-600)", marginTop: 8 }}>
                Cada extractor pasa por <code>utils.extraction_quality.standardize</code>: validación de schema, coerción de tipos, descarte de NULL en columnas críticas, filtro de rangos sanos y deduplicación por clave natural.
              </div>
            </div>
          </div>
        )}

        {/* ── Análisis estadístico ANOVA ───────────────────────────── */}
        <SectionAnova />
      </div>
    </section>
  );
}
