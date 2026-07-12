"use client";
import { useEffect, useState } from "react";
import KpiStrip from "./KpiStrip";
import ColombiaMap from "./charts/ColombiaMap";
import DualLineChart from "./charts/DualLineChart";
import Donut from "./charts/Donut";
import HBars from "./charts/HBars";
import { Icon } from "./icons";

/* ── Plan B: dashboards nativos alimentados por /api/dashboards ───────── */
const COLORS = ["#d97706", "#1e4d7b", "#dc2626", "#1a7a4a", "#7c3aed", "#0891b2"];

function DashboardsNativos() {
  const [data, setData] = useState(null);
  const [err,  setErr]  = useState(false);

  useEffect(() => {
    fetch("/api/dashboards")
      .then((r) => r.json())
      .then(setData)
      .catch(() => setErr(true));
  }, []);

  if (err)   return <div className="card"><div className="card-body">No fue posible cargar los datos.</div></div>;
  if (!data) return <div className="card"><div className="card-body">Cargando dashboards en vivo…</div></div>;

  const donutSegs = data.alertas_por_tipo.map((a, i) => ({
    label: a.tipo, value: a.total, color: COLORS[i % COLORS.length],
  }));
  const topItems  = data.top_municipios.map((m) => ({ l: m.municipio, v: m.rendimiento }));

  return (
    <div className="vista-general">
      <div className="vista-general-banner">
        <span className="vg-icon"><Icon.cpu /></span>
        <div>
          <strong>Modo offline · Charts nativos sobre el star schema</strong>
          <p>Plan B en caso de que Power BI no esté disponible. Datos consultados en runtime desde <code>/api/dashboards</code>.{!data.fromDB && " · Datos de respaldo (BD no disponible)."}</p>
        </div>
      </div>

      <div className="panel-grid-2" style={{ marginTop: 16 }}>
        <div className="card">
          <div className="card-head">
            <div>
              <h3>Real vs. Predicho</h3>
              <div className="panel-sub">Rendimiento medio · t/ha · serie anual</div>
            </div>
            <span className="src-badge">pred_rendimiento + fact_produccion</span>
          </div>
          <div className="card-body">
            <DualLineChart height={300} data={data.serie_rendimiento} />
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <div>
              <h3>Distribución de alertas</h3>
              <div className="panel-sub">{data.alertas_por_tipo.reduce((s, a) => s + a.total, 0)} alertas activas · por tipo</div>
            </div>
            <span className="src-badge">pred_alerta_climatica</span>
          </div>
          <div className="card-body">
            <div className="donut-row">
              <Donut size={200} segments={donutSegs} />
              <div className="bars">
                {data.alertas_por_tipo.map((a, i) => (
                  <div className="bar-item" key={a.tipo}>
                    <div className="bar-meta"><span className="lbl">{a.tipo}</span><span className="val">{a.pct}%</span></div>
                    <div className="bar-track"><span className="bar-fill" style={{ width: `${a.pct}%`, background: COLORS[i % COLORS.length] }}></span></div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {Array.isArray(data.anomalias) && data.anomalias.length > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <div className="card-head">
            <div>
              <h3>🔎 Anomalías detectadas · IsolationForest</h3>
              <div className="panel-sub">Top {data.anomalias.length} predicciones marcadas como atípicas</div>
            </div>
            <span className="src-badge">pred_rendimiento.es_anomalia</span>
          </div>
          <div className="card-body">
            <table className="compare-table">
              <thead><tr><th>Municipio</th><th>Cultivo</th><th>Rendimiento</th><th>Score anomalía</th></tr></thead>
              <tbody>
                {data.anomalias.map((a, i) => (
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
              <h3>Top municipios · rendimiento predicho</h3>
              <div className="panel-sub">Promedio sobre <code>pred_rendimiento</code></div>
            </div>
            <span className="src-badge">pred_rendimiento</span>
          </div>
          <div className="card-body">
            <HBars items={topItems} />
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <div>
              <h3>Semáforo de riesgo</h3>
              <div className="panel-sub">Distribución por nivel</div>
            </div>
            <span className="src-badge">pred_alerta_climatica</span>
          </div>
          <div className="card-body">
            {[
              { l: "Bajo",  v: data.semaforo.bajo,  color: "#1a7a4a" },
              { l: "Medio", v: data.semaforo.medio, color: "#d97706" },
              { l: "Alto",  v: data.semaforo.alto,  color: "#dc2626" },
            ].map((s) => (
              <div className="bar-item" key={s.l} style={{ marginBottom: 12 }}>
                <div className="bar-meta"><span className="lbl">{s.l}</span><span className="val">{s.v}</span></div>
                <div className="bar-track"><span className="bar-fill" style={{ width: `${Math.min(100, s.v)}%`, background: s.color }}></span></div>
              </div>
            ))}
          </div>
        </div>
      </div>
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

/* ── Vista General (mapa real desde /api/mapa) ──────────────────────── */
function VistaGeneral() {
  const [puntos, setPuntos] = useState([]);
  useEffect(() => {
    fetch("/api/mapa").then((r) => r.json()).then(setPuntos).catch(() => setPuntos([]));
  }, []);
  return (
    <div className="vista-general">
      <div className="vista-general-banner">
        <span className="vg-icon"><Icon.cpu /></span>
        <div>
          <strong>Vista general del sistema · Datos ilustrativos</strong>
          <p>Este resumen muestra la capacidad del modelo AgroIA y el alcance territorial del análisis. Los indicadores son referenciales; los datos reales del star schema están disponibles en los dashboards Power BI a continuación.</p>
        </div>
      </div>

      <KpiStrip />
      <div style={{ height: 24 }} />

      <div className="panel-grid-2">
        <div className="card">
          <div className="card-head">
            <div>
              <h3>Distribución territorial</h3>
              <div className="panel-sub">Riesgo agroclimático por municipio</div>
            </div>
            <span className="src-badge">dim_municipio</span>
          </div>
          <div className="card-body">
            <div className="map-frame" style={{ height: 320 }}>
              <ColombiaMap puntos={puntos} height={300} />
            </div>
            <div className="legend-row" style={{ marginTop: 14 }}>
              <span className="legend-dot">Estable (51%)</span>
              <span className="legend-dot amber">Vigilancia (31%)</span>
              <span className="legend-dot red">Alerta (18%)</span>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <div>
              <h3>Real vs. Predicho</h3>
              <div className="panel-sub">Rendimiento medio nacional · t/ha</div>
            </div>
            <span className="src-badge">pred_rendimiento</span>
          </div>
          <div className="card-body">
            <DualLineChart height={300} />
            <div className="summary-strip">
              <span className="ic"><Icon.trend /></span>
              <span><strong>Tendencia al alza sostenida.</strong> El modelo proyecta 5.05 t/ha hacia 2027 con MAE de 0.18 sobre el corredor andino.</span>
            </div>
          </div>
        </div>
      </div>

      <div className="panel-grid-2" style={{ marginTop: 16 }}>
        <div className="card">
          <div className="card-head">
            <div>
              <h3>Distribución de alertas</h3>
              <div className="panel-sub">214 alertas activas · por tipo</div>
            </div>
            <span className="src-badge">pred_alerta_climatica</span>
          </div>
          <div className="card-body">
            <div className="donut-row">
              <Donut size={200} segments={[
                { label: "Sequía",        value: 92, color: "#d97706" },
                { label: "Exceso lluvia", value: 67, color: "#1e4d7b" },
                { label: "Plagas",        value: 38, color: "#dc2626" },
                { label: "Mercado",       value: 17, color: "#1a7a4a" },
              ]} />
              <div className="bars">
                {[
                  { l: "Sequía severa",         v: 43, color: "#d97706" },
                  { l: "Exceso de lluvias",      v: 31, color: "#1e4d7b" },
                  { l: "Plagas y enfermedades",  v: 18, color: "#dc2626" },
                  { l: "Volatilidad de mercado", v: 8,  color: "#1a7a4a" },
                ].map((b) => (
                  <div className="bar-item" key={b.l}>
                    <div className="bar-meta"><span className="lbl">{b.l}</span><span className="val">{b.v}%</span></div>
                    <div className="bar-track"><span className="bar-fill" style={{ width: `${b.v}%`, background: b.color }}></span></div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <div>
              <h3>Top municipios · rendimiento</h3>
              <div className="panel-sub">Maíz tecnificado · 2025 · t/ha</div>
            </div>
            <span className="src-badge">fact_produccion_agricola</span>
          </div>
          <div className="card-body">
            <HBars items={[
              { l: "Espinal, Tolima",  v: 6.2 },
              { l: "Saldaña, Tolima",  v: 5.9 },
              { l: "Aipe, Huila",      v: 5.6 },
              { l: "Yopal, Casanare",  v: 5.4 },
              { l: "Granada, Meta",    v: 5.1 },
              { l: "Ibagué, Tolima",   v: 4.8 },
            ]} />
            <div className="summary-strip">
              <span className="ic"><Icon.check /></span>
              <span>Concentración del top-3 en el corredor andino central. Diferencia de 1.4 t/ha frente a la mediana nacional.</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Página principal ────────────────────────────────────────────────── */
export default function PageDashboards() {
  const [tab, setTab] = useState("panorama_pbi");
  const [modoOffline, setModoOffline] = useState(false);
  const activeCfg = PBI_TABS.find((t) => t.id === tab);

  return (
    <section className="section">
      <div className="container">

        {/* Encabezado de sección */}
        <div className="section-head">
          <span className="eyebrow blue">Dashboards · Power BI</span>
          <h2>Cinco vistas, una sola fuente de verdad</h2>
          <p>Cada tablero combina tablas certificadas del star schema con visualizaciones interactivas. Series actualizadas a corte mensual sobre el pipeline ETL versionado.</p>
        </div>

        {/* Toggle Power BI ↔ Modo offline */}
        <div style={{ display: "flex", justifyContent: "center", gap: 8, marginBottom: 18 }}>
          <button
            className={`tab ${!modoOffline ? "active" : ""}`}
            onClick={() => setModoOffline(false)}
          >
            <Icon.target /> Power BI embebido
          </button>
          <button
            className={`tab ${modoOffline ? "active" : ""}`}
            onClick={() => setModoOffline(true)}
            title="Plan B: charts nativos alimentados desde /api/dashboards"
          >
            <Icon.cpu /> Modo offline · datos en vivo
          </button>
        </div>

        {modoOffline ? (
          <DashboardsNativos />
        ) : (
          <>
            {/* Vista general siempre visible */}
            <VistaGeneral />

        {/* Separador hacia los dashboards reales */}
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
            Dashboards Power BI · Datos reales del star schema
          </span>
          <div className="pbi-divider-line" />
        </div>

        {/* Tabs de Power BI */}
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

        {/*
          Un solo iframe persistente — el src nunca cambia,
          React no lo recarga al cambiar de tab.
          Solo el header (label + indicador de página) se actualiza.
        */}
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
              frameBorder="0"
              allowFullScreen
              className="pbi-iframe"
            />
          </div>
        </div>
          </>
        )}

      </div>
    </section>
  );
}
