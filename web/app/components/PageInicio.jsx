"use client";
import Hero from "./Hero";
import KpiStrip from "./KpiStrip";
import ColombiaMap from "./charts/ColombiaMap";
import DualLineChart from "./charts/DualLineChart";
import { EmptyState, Estado } from "./ui/Estados";
import DataStamp from "./ui/DataStamp";
import PreciosHoy from "./PreciosHoy";
import Term from "./ui/Term";
import { useApi } from "@/lib/useApi";

const fmt = (n, d = 0) => (n == null ? "—" : Number(n).toLocaleString("es-CO", { maximumFractionDigits: d }));

const SEMAFORO = [
  { clave: "alto",  lbl: "Alto",  desc: "Riesgo climático crítico",   clase: "red",   color: "var(--red-600)" },
  { clave: "medio", lbl: "Medio", desc: "Factores a vigilar",         clase: "amber", color: "var(--amber-600)" },
  { clave: "bajo",  lbl: "Bajo",  desc: "Condiciones favorables",     clase: "green", color: "var(--green-600)" },
];

export default function PageInicio({ onNav }) {
  const mapa = useApi("/api/mapa");
  const dash = useApi("/api/dashboards");
  const modelo = useApi("/api/modelo/metricas");

  const puntos = Array.isArray(mapa.data) ? mapa.data : [];
  const conteo = (r) => puntos.filter((p) => p.riesgo === r).length;

  return (
    <>
      <Hero onNav={onNav} />

      <section className="section section-gray" style={{ paddingTop: 64, paddingBottom: 56 }}>
        <KpiStrip />
      </section>

      <PreciosHoy onNav={onNav} />

      <section className="section">
        <div className="container">
          <div className="section-head">
            <span className="eyebrow">Vista rápida del sistema</span>
            <h2>Tres lentes sobre el agro colombiano</h2>
            <p>Mapa de alertas, evolución del rendimiento y semáforo de riesgo, calculados en vivo sobre las tablas del sistema. Cada tarjeta indica su fuente.</p>
          </div>

          <div className="qv-grid">
            <div className="card">
              <div className="card-head">
                <div>
                  <h3>Mapa de alertas</h3>
                  <div className="panel-sub">Municipios con alerta climática activa</div>
                </div>
                <span className="src-badge">pred_alerta_climatica</span>
              </div>
              <div className="card-body">
                <Estado api={mapa}>
                  {() => puntos.length === 0 ? (
                    <EmptyState titulo="Sin alertas activas" texto="No hay municipios con alertas climáticas vigentes." />
                  ) : (
                    <>
                      <div className="map-frame"><ColombiaMap puntos={puntos} height={260} /></div>
                      <div className="legend-row">
                        <span className="legend-dot">Bajo ({conteo("BAJO")})</span>
                        <span className="legend-dot amber">Medio ({conteo("MEDIO")})</span>
                        <span className="legend-dot red">Alto ({conteo("ALTO")})</span>
                      </div>
                    </>
                  )}
                </Estado>
                <DataStamp fuente="dim_municipio + pred_alerta_climatica" nota="hasta 120 municipios, los de mayor probabilidad" />
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
                  {(d) => {
                    const serie = d.serie_rendimiento || [];
                    const ultimoReal = [...serie].reverse().find((s) => s.real != null);
                    const r = modelo.data?.rendimiento;
                    return (
                      <>
                        <div className="chart-frame"><DualLineChart height={200} data={serie} /></div>
                        <div className="chart-metrics">
                          <div className="chart-metric"><div className="v">{ultimoReal ? fmt(ultimoReal.real, 2) : "—"}</div><div className="l">{ultimoReal ? `t/ha real ${ultimoReal.anio}` : "t/ha real"}</div></div>
                          <div className="chart-metric"><div className="v">{r?.mae_t_ha != null ? `±${fmt(r.mae_t_ha, 2)}` : "—"}</div><div className="l"><Term id="MAE">Error típico</Term> (<Term id="t/ha" />)</div></div>
                          <div className="chart-metric"><div className="v">{r?.r2 != null ? `R²=${fmt(r.r2, 2)}` : "—"}</div><div className="l">Validación (<a href="#datos">ver ficha</a>)</div></div>
                        </div>
                      </>
                    );
                  }}
                </Estado>
                <DataStamp fuente="pred_rendimiento + fact_produccion_agricola" fecha={modelo.data?.rendimiento?.entrenado} nota="métricas del último entrenamiento" />
              </div>
            </div>

            <div className="card">
              <div className="card-head">
                <div>
                  <h3>Semáforo de riesgo</h3>
                  <div className="panel-sub">Distribución nacional de alertas activas</div>
                </div>
                <span className="src-badge">pred_alerta_climatica</span>
              </div>
              <div className="card-body">
                <Estado api={dash}>
                  {(d) => {
                    const s = d.semaforo || {};
                    const total = (s.alto || 0) + (s.medio || 0) + (s.bajo || 0);
                    if (!total) return <EmptyState titulo="Sin alertas" texto="No hay alertas activas registradas." />;
                    return SEMAFORO.map((n) => {
                      const pct = Math.round(((s[n.clave] || 0) / total) * 100);
                      return (
                        <div className={`risk-row ${n.clase}`} key={n.clave}>
                          <span className={`risk-dot ${n.clase}`}></span>
                          <div className="risk-info">
                            <div className="lbl">{n.lbl} · {fmt(s[n.clave])}</div>
                            <div className="desc">{n.desc}</div>
                            <div className="risk-bar"><span style={{ width: `${pct}%`, background: n.color }}></span></div>
                          </div>
                          <div className="risk-pct">{pct}%</div>
                        </div>
                      );
                    });
                  }}
                </Estado>
                <DataStamp fuente="pred_alerta_climatica" nota="índice de riesgo por reglas" />
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="section section-gray">
        <div className="container">
          <div className="section-head">
            <span className="eyebrow">Cómo funciona</span>
            <h2>De datos abiertos a decisiones territoriales</h2>
            <p>La solución se organiza en tres capas que responden a distintos perfiles de usuario y momentos de interacción con el sistema.</p>
          </div>
          <div className="steps">
            <div className="step">
              <div className="step-head">
                <div className="step-num">1</div>
                <span className="step-pill">Capa narrativa</span>
              </div>
              <h3>Datos abiertos</h3>
              <p>Consolidamos series del DANE, IDEAM, UPRA y SIPSA con frecuencia mensual y municipal, armonizadas en un star schema único. La pestaña Precios agrega precios mayoristas diarios.</p>
            </div>
            <div className="step">
              <div className="step-head">
                <div className="step-num">2</div>
                <span className="step-pill">Capa analítica</span>
              </div>
              <h3>Analítica y modelos</h3>
              <p>Tres vistas de Power BI cubren panorama ejecutivo, producción y clima. Un modelo XGBoost predice rendimiento; sus métricas de validación se publican en las tarjetas y en Metodología.</p>
            </div>
            <div className="step">
              <div className="step-head">
                <div className="step-num">3</div>
                <span className="step-pill">Capa predictiva</span>
              </div>
              <h3>Apoyo a decisión</h3>
              <p>Consulta puntual por municipio, cultivo y período. Devuelve rendimiento esperado, nivel de riesgo y explicación en lenguaje simple para la toma de decisión operativa.</p>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
