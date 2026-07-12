"use client";
import { useEffect, useState } from "react";
import Hero from "./Hero";
import { Icon } from "./icons";

function fmtNumber(n) {
  if (n == null) return "—";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, "") + "M";
  if (n >= 1_000)     return (n / 1_000).toFixed(1).replace(/\.0$/, "") + "k";
  return n.toLocaleString("es-CO");
}

const ALIADOS = [
  { nombre: "MinAgricultura",   rol: "Política pública",   valor: "Insumo cuantitativo para planes departamentales de seguridad alimentaria." },
  { nombre: "Agrosavia",        rol: "Investigación",      valor: "Validación científica de modelos y co-diseño de features agronómicos." },
  { nombre: "FEDEARROZ · FNC",  rol: "Gremios",            valor: "Despliegue del predictor a productores afiliados de arroz y café." },
  { nombre: "UPRA",             rol: "Aptitud territorial", valor: "Cruce con SIPRA para recomendar zonas de expansión sostenible." },
  { nombre: "IDEAM",            rol: "Clima",              valor: "Realimentación bidireccional: alertas tempranas como capa adicional al IDEAM." },
  { nombre: "Gobernaciones",    rol: "Implementación",     valor: "Tableros embebidos en oficinas técnicas de planeación rural." },
];

export default function PageImpacto({ onNav }) {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    fetch("/api/impacto")
      .then((r) => r.json())
      .then((d) => setStats(d))
      .catch(() => setStats(null));
  }, []);

  const municipios  = stats?.municipios_cubiertos;
  const cultivos    = stats?.cultivos_monitoreados;
  const hectareas   = stats?.hectareas_cobertura;
  const productores = stats?.productores_potenciales;
  const altoRiesgo  = stats?.alertas_alto_riesgo;
  const rendProm    = stats?.rendimiento_promedio;

  return (
    <>
      <Hero onNav={onNav} compact />

      <section className="section">
        <div className="container">
          <div className="section-head">
            <span className="eyebrow amber">Impacto</span>
            <h2>Cobertura medible y escalabilidad nacional</h2>
            <p>Métricas calculadas en tiempo real sobre el star schema. Sin cifras infladas: lo que ves es el alcance real del modelo y su potencial de despliegue.</p>
          </div>

          <div className="impact-grid">
            <div className="impact-card">
              <div className="icon-wrap"><Icon.building /></div>
              <h3>Cobertura territorial</h3>
              <p>Municipios con al menos una predicción activa o registro histórico de producción en la base de datos.</p>
              <div className="impact-stat-row">
                <div className="impact-stat">{fmtNumber(municipios)}</div>
                <div className="impact-stat-label">Municipios<br />en el modelo</div>
              </div>
            </div>

            <div className="impact-card amber">
              <div className="icon-wrap"><Icon.wheat /></div>
              <h3>Cultivos monitoreados</h3>
              <p>Diversidad de cultivos transitorios y permanentes con rendimientos predichos por XGBoost.</p>
              <div className="impact-stat-row">
                <div className="impact-stat">{fmtNumber(cultivos)}</div>
                <div className="impact-stat-label">Cultivos en<br />dim_cultivo</div>
              </div>
            </div>

            <div className="impact-card blue">
              <div className="icon-wrap"><Icon.layers /></div>
              <h3>Hectáreas bajo cobertura</h3>
              <p>Sumatoria del área sembrada en los registros de producción agregados por el pipeline ETL.</p>
              <div className="impact-stat-row">
                <div className="impact-stat">{fmtNumber(hectareas)}</div>
                <div className="impact-stat-label">ha integradas en<br />fact_produccion_agricola</div>
              </div>
            </div>

            <div className="impact-card green-light">
              <div className="icon-wrap"><Icon.users /></div>
              <h3>Productores potenciales</h3>
              <p>Estimado a partir del Censo Nacional Agropecuario y promedio de hectáreas por unidad productiva agropecuaria.</p>
              <div className="impact-stat-row">
                <div className="impact-stat">{fmtNumber(productores)}</div>
                <div className="impact-stat-label">Beneficiarios<br />potenciales</div>
              </div>
            </div>
          </div>

          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginTop: 22, color: "var(--gray-600)", fontSize: 13 }}>
            <span>📡 Alertas de alto riesgo activas: <strong>{fmtNumber(altoRiesgo)}</strong></span>
            <span>📈 Rendimiento promedio nacional predicho: <strong>{rendProm != null ? `${rendProm} t/ha` : "—"}</strong></span>
            {stats?.fromDB === false && (
              <span style={{ color: "#d97706" }}>⚠ Cifras de respaldo · BD no disponible</span>
            )}
          </div>
        </div>
      </section>

      <section className="section section-gray">
        <div className="container">
          <div className="section-head">
            <span className="eyebrow blue">Aliados objetivo</span>
            <h2>Plan de adopción por stakeholder</h2>
            <p>AgroIA no afirma adopciones que no existen. Esta es la propuesta de valor para cada actor del sistema agroalimentario colombiano.</p>
          </div>
          <div className="impact-grid">
            {ALIADOS.map((a) => (
              <div key={a.nombre} className="impact-card">
                <div className="icon-wrap"><Icon.shield /></div>
                <h3>{a.nombre}</h3>
                <div style={{ fontSize: 11, fontWeight: 600, color: "var(--blue-700)", textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 6 }}>{a.rol}</div>
                <p>{a.valor}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="section-head">
            <span className="eyebrow green">Sostenibilidad</span>
            <h2>Costos, financiación y continuidad</h2>
            <p>AgroIA está diseñada para correr sobre infraestructura asequible y replicable. Estos son los costos reales del despliegue actual y las vías de financiación viables para escalarlo a nivel nacional.</p>
          </div>

          <div className="impact-grid" style={{ marginBottom: 28 }}>
            <div className="impact-card">
              <div className="icon-wrap"><Icon.layers /></div>
              <h3>Costo operativo mensual</h3>
              <p>Despliegue en free / hobby tiers durante la fase de validación. Escalable a planes pagos sólo cuando el tráfico lo justifique.</p>
              <ul style={{ fontSize: 13, color: "var(--gray-700)", marginTop: 8, paddingLeft: 18 }}>
                <li>Supabase (PostgreSQL + Auth) — <strong>USD 0–25</strong></li>
                <li>Vercel (Next.js) — <strong>USD 0–20</strong></li>
                <li>Groq (Llama 3.3 70B) — <strong>USD 0</strong> en free tier</li>
                <li>GitHub Actions cron ETL — <strong>USD 0</strong> (2k min/mes)</li>
              </ul>
              <div className="impact-stat-row">
                <div className="impact-stat">≤ USD 45</div>
                <div className="impact-stat-label">Costo mensual<br />fase MVP</div>
              </div>
            </div>

            <div className="impact-card blue">
              <div className="icon-wrap"><Icon.building /></div>
              <h3>Vías de financiación</h3>
              <p>Cofinanciación pública + alianzas con gremios para sostener la operación más allá del MVP universitario.</p>
              <ul style={{ fontSize: 13, color: "var(--gray-700)", marginTop: 8, paddingLeft: 18 }}>
                <li>MinTIC — convocatorias de IA y datos abiertos</li>
                <li>BID Lab — innovación agro-tech en LATAM</li>
                <li>Regalías SGR — proyectos CTeI departamentales</li>
                <li>Fedearroz / FNC — co-inversión por valor recibido</li>
              </ul>
            </div>

            <div className="impact-card amber">
              <div className="icon-wrap"><Icon.shield /></div>
              <h3>Continuidad técnica</h3>
              <p>Pipeline reproducible, datos abiertos como única fuente y código en GitHub aseguran que el proyecto sobreviva al equipo original.</p>
              <ul style={{ fontSize: 13, color: "var(--gray-700)", marginTop: 8, paddingLeft: 18 }}>
                <li>Pipeline ETL totalmente automatizado</li>
                <li>Schema versionado en <code>load/schema.sql</code></li>
                <li>Modelos entrenables con un comando</li>
                <li>Documentación de reproducción en README</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="section-head" style={{ marginBottom: 22 }}>
            <span className="eyebrow">Demo · Guía para el jurado</span>
            <h2>Secuencia narrativa recomendada</h2>
            <p>Una ruta de cinco pasos que conecta el problema público con la solución técnica y el impacto potencial.</p>
          </div>
          <div className="demo-list">
            {[
              { n: "01", txt: <>Presenta el <strong>problema público</strong> del sector agropecuario colombiano en planificación y riesgo, y abre con los KPIs del Inicio.</>, tag: "Contexto",  page: "inicio",      cta: "Ir a Inicio →" },
              { n: "02", txt: <>Muestra la integración de <strong>datos abiertos</strong>: catálogo Socrata, Hoja de Ruta Sectorial Agropecuaria y trazabilidad por dataset.</>, tag: "Datos",     page: "metodologia", cta: "Ver catálogo →" },
              { n: "03", txt: <>Navega los <strong>dashboards</strong>: panorama ejecutivo, real vs. predicho, semáforo, alertas y anomalías. Activa el modo offline si es necesario.</>, tag: "Analítica", page: "dashboards",  cta: "Abrir dashboards →" },
              { n: "04", txt: <>Ejecuta una <strong>predicción puntual</strong>, muestra el panel SHAP con los 3 factores y la <strong>recomendación accionable</strong>.</>, tag: "Producto",  page: "prediccion",  cta: "Probar predicción →", amber: true },
              { n: "05", txt: <>Pregúntale al <strong>asistente</strong> por voz: "compara Espinal y Saldaña" o "qué pasa si hay El Niño en Pasto".</>, tag: "Agente IA", page: "asistente",    cta: "Hablar con AgroIA →", amber: true },
              { n: "06", txt: <>Cierra con <strong>aliados objetivo</strong>, <strong>impacto medible</strong> y plan de sostenibilidad económica.</>, tag: "Cierre",    page: null,           cta: null,                    amber: true },
            ].map((step) => (
              <div key={step.n} className={`demo-item ${step.amber ? "amber" : ""}`} style={{ display: "flex", alignItems: "center", gap: 14 }}>
                <div className="num">{step.n}</div>
                <div className="txt" style={{ flex: 1 }}>{step.txt}</div>
                <span className="tag">{step.tag}</span>
                {step.page && (
                  <button
                    onClick={() => onNav && onNav(step.page)}
                    style={{
                      fontSize: 12,
                      fontWeight: 600,
                      padding: "6px 12px",
                      borderRadius: 6,
                      border: "1px solid var(--blue-700)",
                      background: "white",
                      color: "var(--blue-700)",
                      cursor: "pointer",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {step.cta}
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
