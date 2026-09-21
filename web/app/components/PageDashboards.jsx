"use client";
import { useState } from "react";
import KpiStrip from "./KpiStrip";
import ColombiaMap from "./charts/ColombiaMap";
import DualLineChart from "./charts/DualLineChart";
import Donut from "./charts/Donut";
import HBars from "./charts/HBars";
import { EmptyState, Estado } from "./ui/Estados";
import DataStamp from "./ui/DataStamp";
import { Icon } from "./icons";
import { useApi } from "@/lib/useApi";

const COLORS = ["#d97706", "#1e4d7b", "#dc2626", "#1a7a4a", "#7c3aed", "#0891b2"];
const fmt = (n, d = 0) => (n == null ? "—" : Number(n).toLocaleString("es-CO", { maximumFractionDigits: d }));

/* ── Resumen en vivo: todo sale de /api/dashboards, /api/mapa y /api/modelo/metricas ───────────── */
function ResumenEnVivo() {
  const dash = useApi("/api/dashboards");
  const mapa = useApi("/api/mapa");
  const modelo = useApi("/api/modelo/metricas");
  const puntos = Array.isArray(mapa.data) ? mapa.data : [];
  const m = modelo.data?.rendimiento;

  return (
    <div className="vista-general">
      <div className="vista-general-banner">
        <span className="vg-icon"><Icon.cpu /></span>
        <div>
          <strong>Resumen en vivo · datos reales del sistema</strong>
          <p>Cada tarjeta se calcula al momento sobre las tablas del star schema y muestra su fuente. Si un dato no existe, se indica; no se rellena con valores de ejemplo.</p>
        </div>
      </div>

      <KpiStrip />
      <div style={{ height: 24 }} />

      <div className="panel-grid-2">
        <div className="card">
          <div className="card-head">
            <div>
              <h3>Distribución territorial</h3>
              <div className="panel-sub">Municipios con alerta climática activa</div>
            </div>
            <span className="src-badge">pred_alerta_climatica</span>
          </div>
          <div className="card-body">
            <Estado api={mapa}>
              {() => puntos.length === 0 ? (
                <EmptyState titulo="Sin alertas activas" texto="No hay municipios con alertas vigentes." />
              ) : (
                <>
                  <div className="map-frame" style={{ height: 320 }}><ColombiaMap puntos={puntos} height={300} /></div>
                  <div className="legend-row" style={{ marginTop: 14 }}>
                    <span className="legend-dot">Bajo ({puntos.filter((p) => p.riesgo === "BAJO").length})</span>
                    <span className="legend-dot amber">Medio ({puntos.filter((p) => p.riesgo === "MEDIO").length})</span>
                    <span className="legend-dot red">Alto ({puntos.filter((p) => p.riesgo === "ALTO").length})</span>
                  </div>
                </>
              )}
            </Estado>
            <DataStamp fuente="dim_municipio + pred_alerta_climatica" />
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <div>
              <h3>Rendimiento real vs. modelo</h3>
              <div className="panel-sub">Promedio de todos los cultivos · t/ha</div>
            </div>
            <span className="src-badge">pred_rendimiento</span>
          </div>
          <div className="card-body">
            <Estado api={dash}>
              {(d) => (
                <>
                  <DualLineChart height={300} data={d.serie_rendimiento} />
                  {m && (
                    <div className="summary-strip">
                      <span className="ic"><Icon.trend /></span>
                      <span>Error típico del modelo en validación: <strong>±{fmt(m.mae_t_ha, 2)} t/ha</strong>{m.r2 != null && <> · R² = <strong>{fmt(m.r2, 2)}</strong></>}. Promedia cultivos con rendimientos muy distintos: para un cultivo concreto usa la pestaña Predicción.</span>
                    </div>
                  )}
                </>
              )}
            </Estado>
            <DataStamp fuente="pred_rendimiento + fact_produccion_agricola" fecha={m?.entrenado} nota="métricas del último entrenamiento" />
          </div>
        </div>
      </div>

      <Estado api={dash}>
        {(d) => {
          const totalAlertas = d.alertas_por_tipo.reduce((s, a) => s + a.total, 0);
          const donutSegs = d.alertas_por_tipo.map((a, i) => ({ label: a.tipo, value: a.total, color: COLORS[i % COLORS.length] }));
          const topItems = d.top_municipios.map((x) => ({ l: x.municipio, v: x.rendimiento }));
          const s = d.semaforo;
          return (
            <>
              {Array.isArray(d.anomalias) && d.anomalias.length > 0 && (
                <div className="card" style={{ marginTop: 16 }}>
                  <div className="card-head">
                    <div>
                      <h3>Anomalías detectadas · IsolationForest</h3>
                      <div className="panel-sub">Top {d.anomalias.length} predicciones marcadas como atípicas</div>
                    </div>
                    <span className="src-badge">pred_rendimiento.es_anomalia</span>
                  </div>
                  <div className="card-body">
                    <table className="compare-table">
                      <thead><tr><th>Municipio</th><th>Cultivo</th><th>Rendimiento</th><th>Score anomalía</th></tr></thead>
                      <tbody>
                        {d.anomalias.map((a, i) => (
                          <tr key={i}>
                            <td><strong>{a.municipio}</strong></td>
                            <td>{a.cultivo}</td>
                            <td className="num">{a.rendimiento} <span className="muted" style={{ fontSize: 11 }}>t/ha</span></td>
                            <td className="num" style={{ color: "#dc2626" }}>{a.score}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              <div className="panel-grid-2" style={{ marginTop: 16 }}>
                <div className="card">
                  <div className="card-head">
                    <div>
                      <h3>Distribución de alertas</h3>
                      <div className="panel-sub">{fmt(totalAlertas)} alertas activas · por tipo</div>
                    </div>
                    <span className="src-badge">pred_alerta_climatica</span>
                  </div>
                  <div className="card-body">
                    {totalAlertas === 0 ? <EmptyState titulo="Sin alertas" texto="No hay alertas activas registradas." /> : (
                      <div className="donut-row">
                        <Donut size={200} segments={donutSegs} />
                        <div className="bars">
                          {d.alertas_por_tipo.map((a, i) => (
                            <div className="bar-item" key={a.tipo}>
                              <div className="bar-meta"><span className="lbl">{a.tipo}</span><span className="val">{a.pct}%</span></div>
                              <div className="bar-track"><span className="bar-fill" style={{ width: `${a.pct}%`, background: COLORS[i % COLORS.length] }}></span></div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    <DataStamp fuente="pred_alerta_climatica" />
                  </div>
                </div>

                <div className="card">
                  <div className="card-head">
                    <div>
                      <h3>Top municipios · rendimiento predicho</h3>
                      <div className="panel-sub">Promedio sobre <code>pred_rendimiento</code> (todos los cultivos)</div>
                    </div>
                    <span className="src-badge">pred_rendimiento</span>
                  </div>
                  <div className="card-body">
                    {topItems.length === 0 ? <EmptyState titulo="Sin predicciones" /> : <HBars items={topItems} />}
                    <DataStamp fuente="pred_rendimiento" />
                  </div>
                </div>
              </div>

              <div className="card" style={{ marginTop: 16 }}>
                <div className="card-head">
                  <div>
                    <h3>Semáforo de riesgo</h3>
                    <div className="panel-sub">Alertas activas por nivel</div>
                  </div>
                  <span className="src-badge">pred_alerta_climatica</span>
                </div>
                <div className="card-body">
                  {[
                    { l: "Bajo", v: s.bajo, color: "#1a7a4a" },
                    { l: "Medio", v: s.medio, color: "#d97706" },
                    { l: "Alto", v: s.alto, color: "#dc2626" },
                  ].map((x) => {
                    const total = (s.bajo || 0) + (s.medio || 0) + (s.alto || 0) || 1;
                    return (
                      <div className="bar-item" key={x.l} style={{ marginBottom: 12 }}>
                        <div className="bar-meta"><span className="lbl">{x.l}</span><span className="val">{fmt(x.v)}</span></div>
                        <div className="bar-track"><span className="bar-fill" style={{ width: `${Math.round(((x.v || 0) / total) * 100)}%`, background: x.color }}></span></div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          );
        }}
      </Estado>
    </div>
  );
}

const BASE_PBI = "https://app.powerbi.com/view?r=eyJrIjoiYTU5ODY5MmMtNzVmNy00MTQ0LWFhODItZTg0ODIzNDI0MTk5IiwidCI6IjhkMzY4MzZlLTZiNzUtNGRlNi1iYWI5LTVmNGIxNzc1NDI3ZiIsImMiOjR9";

const PBI_TABS = [
  { id: "panorama_pbi", label: "Panorama Ejecutivo", pageNum: 1, pageName: "56b0cd0922bc5dea7a03" },
  { id: "produccion",   label: "Producción",          pageNum: 2, pageName: "d1e8cfb98623cb22537b" },
  { id: "clima",        label: "Clima & Alertas",     pageNum: 3, pageName: "763fb90f5adea074007a" },
];

function getPbiUrl(cfg) {
  return cfg.pageName ? `${BASE_PBI}&pageName=${cfg.pageName}` : BASE_PBI;
}

const TAB_ICONS = {
  panorama_pbi: <Icon.target />,
  produccion:   <Icon.wheat />,
  clima:        <Icon.drop />,
};

/* ── Página principal ────────────────────────────────────────────────── */
export default function PageDashboards() {
  const [tab, setTab] = useState("panorama_pbi");
  const activeCfg = PBI_TABS.find((t) => t.id === tab);

  return (
    <section className="section">
      <div className="container">

        <div className="section-head">
          <span className="eyebrow blue">Dashboards</span>
          <h2>Resumen en vivo y tres vistas de Power BI</h2>
          <p>Primero, un resumen calculado al momento sobre el star schema; debajo, los tableros interactivos de Power BI. Los datos de Power BI se actualizan con el corte mensual del pipeline ETL.</p>
        </div>

        <ResumenEnVivo />

        <div className="pbi-section-divider">
          <div className="pbi-divider-line" />
          <span className="pbi-divider-label">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
              <line x1="3" y1="9" x2="21" y2="9"/>
              <line x1="3" y1="15" x2="21" y2="15"/>
              <line x1="9" y1="3" x2="9" y2="21"/>
              <line x1="15" y1="3" x2="15" y2="21"/>
            </svg>
            Dashboards Power BI · Datos del star schema
          </span>
          <div className="pbi-divider-line" />
        </div>

        <div className="tabs">
          {PBI_TABS.map((t) => (
            <button
              key={t.id}
              className={`tab ${tab === t.id ? "active" : ""}`}
              onClick={() => setTab(t.id)}
            >
              <span style={{ display: "inline-flex" }}>{TAB_ICONS[t.id]}</span>
              {t.label}
            </button>
          ))}
        </div>

        {/* Un solo iframe persistente: el src cambia solo de página, no se recarga el informe. */}
        <div className="pbi-panel">
          <div className="pbi-header">
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span className="pbi-badge">Power BI</span>
              <span className="pbi-page-label">{activeCfg.label}</span>
              <span className="pbi-page-num">Página {activeCfg.pageNum} / 3</span>
            </div>
            <a href={getPbiUrl(activeCfg)} target="_blank" rel="noopener noreferrer" className="pbi-open-btn">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                <polyline points="15 3 21 3 21 9"/>
                <line x1="10" y1="14" x2="21" y2="3"/>
              </svg>
              Pantalla completa
            </a>
          </div>
          <div className="pbi-frame-wrap">
            <iframe
              key={activeCfg.id}
              title={`dashboard-${activeCfg.id}`}
              src={getPbiUrl(activeCfg)}
              loading="lazy"
              frameBorder="0"
              allowFullScreen
              className="pbi-iframe"
            />
          </div>
        </div>

      </div>
    </section>
  );
}
