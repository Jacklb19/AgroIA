"use client";
import { useEffect, useState } from "react";
import { Icon } from "./icons";

/* ─── Metadata editorial de cada prueba ANOVA ─────────────────────────────── */
const ANOVA_TESTS = [
  {
    id: 1,
    imagen: "anova_precipitacion_enso.png",
    titulo: "Lluvia y fenómeno El Niño / La Niña",
    pregunta: "¿Llueve diferente según el estado del clima global?",
    explicacion:
      "Comparamos cuánto llueve en Colombia durante tres fases climáticas: El Niño (calentamiento del Pacífico), La Niña (enfriamiento) y años Neutros. El resultado confirma que las diferencias son reales y no por azar: durante La Niña llueve bastante más que durante El Niño. Esto explica por qué los años con El Niño suelen traer sequía y mayores pérdidas en los cultivos.",
    fuente: "IDEAM · 47 819 registros",
    color: "#1e4d7b",
    colorLight: "#e8f0f7",
  },
  {
    id: 2,
    imagen: "anova_precio_tipo_insumo.png",
    titulo: "Precio de insumos según su tipo",
    pregunta: "¿Cuestan lo mismo los fertilizantes, las semillas y los agroquímicos?",
    explicacion:
      "Comparamos el precio de cinco categorías de insumos agrícolas (fertilizantes, agroquímicos, semillas, combustible y mano de obra). El análisis confirma que los precios son significativamente distintos entre sí. El fertilizante es el insumo con precio más alto en promedio. Esta diferencia es importante para que los agricultores puedan planificar mejor sus costos.",
    fuente: "DANE · SIPSA · 5 472 registros",
    color: "#b45309",
    colorLight: "#fef5e7",
  },
  {
    id: 3,
    imagen: "anova_precipitacion_trimestre.png",
    titulo: "Lluvias según la época del año",
    pregunta: "¿Hay meses con más lluvia que otros en Colombia?",
    explicacion:
      "Colombia tiene dos épocas lluviosas al año (régimen bimodal). Dividimos el año en cuatro trimestres y confirmamos estadísticamente que sí existen diferencias significativas de precipitación entre ellos. Los trimestres de abril–junio y octubre–diciembre son los más lluviosos. Conocer este patrón ayuda a programar mejor la siembra y la cosecha.",
    fuente: "IDEAM · 47 819 registros",
    color: "#155436",
    colorLight: "#ecf7f0",
  },
  {
    id: 4,
    imagen: "anova_precipitacion_nasa_municipios.png",
    titulo: "Lluvia en tres ciudades colombianas (datos NASA)",
    pregunta: "¿Llueve igual en Ibagué, Pasto y Villavicencio?",
    explicacion:
      "Usamos datos del satélite de la NASA (sistema MERRA-2, diferente a las estaciones terrestres del IDEAM) para comparar la precipitación diaria en tres ciudades con climas distintos durante 2024. El resultado muestra que Villavicencio (Llanos Orientales) llueve significativamente más que Ibagué (zona andina de Tolima) y Pasto (sur andino de Nariño). Esto valida que diferentes fuentes de datos capturan correctamente las diferencias climáticas regionales.",
    fuente: "NASA POWER MERRA-2 · 1 098 registros diarios",
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
  const row = datos.find((r) => r["Prueba"]?.includes(test.id === 1 ? "ENSO" : test.id === 2 ? "Tipo" : test.id === 3 ? "Trimestre" : "NASA"));

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
        <div style={{ fontSize: 11, color: "var(--ink-400)", borderTop: "1px solid var(--ink-100)", paddingTop: 8 }}>
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
                <span>F-estadístico</span><span style={{ color: "var(--ink-900)", fontWeight: 600 }}>{parseFloat(row["F"]).toFixed(3)}</span>
                <span>p-valor</span><span style={{ color: parseFloat(row["p-valor"]) < 0.05 ? "#155436" : "var(--ink-600)", fontWeight: 600 }}>{parseFloat(row["p-valor"]) < 0.0001 ? "< 0.0001" : row["p-valor"]}</span>
                <span>Grupos</span><span>{row["Grupos"]}</span>
                <span>N total</span><span>{parseInt(row["N total"]).toLocaleString("es-CO")}</span>
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
          <h3>Análisis estadístico — Pruebas ANOVA</h3>
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
              ANOVA es una prueba matemática que nos dice si las diferencias que vemos entre grupos de datos son <strong>reales</strong> o simplemente producto del azar. Por ejemplo: si llueve más durante La Niña que en El Niño, ¿es una diferencia consistente o fue casualidad de ese año? Cada prueba abajo responde una pregunta concreta con evidencia estadística. El símbolo <strong>***</strong> indica que la diferencia es altamente significativa (probabilidad menor al 0.1% de que sea azar).
            </p>
          </div>
        </div>

        {/* Grid de 4 pruebas */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))",
          gap: 20,
        }}>
          {ANOVA_TESTS.map((test) => (
            <AnovaCard key={test.id} test={test} datos={datos} />
          ))}
        </div>

        {/* Nota protocolo */}
        <div style={{ fontSize: 11.5, color: "var(--ink-500)", marginTop: 18, lineHeight: 1.6 }}>
          <strong>Protocolo estadístico:</strong> cada prueba ejecuta (1) Levene para verificar homogeneidad de varianzas, (2) ANOVA de una vía con <code>scipy.stats.f_oneway</code>, y (3) Tukey HSD post-hoc cuando p &lt; 0.05 para identificar qué pares de grupos difieren. Gráficos generados con matplotlib · boxplots con n por grupo.
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
  useEffect(() => {
    fetch("/api/catalogo").then((r) => r.json()).then(setFuentes).catch(() => setFuentes([]));
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
              <li>Detección de outliers por z-score robusto</li>
              <li>Feature store en Parquet versionado</li>
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
              <li>XGBoost con tuning bayesiano (Optuna · 200 trials)</li>
              <li>~40 features: clima estacional + lags 1y/3y + ENSO + SIPSA + SIPRA</li>
              <li>Hold-out temporal por año + TimeSeriesSplit 5-fold</li>
              <li>Inferencia sobre municipios × cultivos del star schema</li>
            </ul>
          </div>
          <div className="method-card amber">
            <div className="icon-wrap"><Icon.ruler /></div>
            <h3>Validación y métricas</h3>
            <ul>
              <li>Métricas reales en <code>model_version.metricas_json</code></li>
              <li>Train: años &lt; 80% percentil · Test: últimos 20%</li>
              <li>Reporta MAE, RMSE, R², CV-MAE de Optuna</li>
              <li>Banda de confianza ± MAE en cada predicción</li>
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
              <h3>XGBoost vs. baselines</h3>
              <p>Hold-out temporal · evaluación sobre los últimos años disponibles.</p>
            </div>
            <span className="src-badge">model_version · activo</span>
          </div>
          <table className="metrics-table">
            <thead>
              <tr><th>Modelo</th><th colSpan={3}>Métricas</th><th>Notas</th></tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>XGBoost — campeón</strong> <span className="winner-cell">activo</span></td>
                <td className="num best" colSpan={3} style={{ textAlign: "left", fontFamily: "var(--font-mono)", fontSize: 12 }}>
                  Métricas dinámicas — ver <code>model_version.metricas_json</code> tras cada entrenamiento.
                </td>
                <td className="num best" style={{ fontSize: 11 }}>Optuna 200 trials · TS-Split 5</td>
              </tr>
              <tr>
                <td>Regresión lineal multivariada</td>
                <td className="num mid" colSpan={3}>Baseline interpretable</td>
                <td className="num mid" style={{ fontSize: 11 }}>Referencia</td>
              </tr>
              <tr>
                <td>Promedio móvil quinquenal (naive)</td>
                <td className="num worst" colSpan={3}>Baseline mínimo</td>
                <td className="num worst" style={{ fontSize: 11 }}>Línea base</td>
              </tr>
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
