"use client";
import { useEffect, useState } from "react";
import Hero from "./Hero";
import KpiStrip from "./KpiStrip";
import ColombiaMap from "./charts/ColombiaMap";
import Sparkline from "./charts/Sparkline";
import { Icon } from "./icons";

export default function PageInicio({ onNav }) {
  const [puntos, setPuntos] = useState([]);
  useEffect(() => {
    fetch("/api/mapa").then((r) => r.json()).then(setPuntos).catch(() => setPuntos([]));
  }, []);

  return (
    <>
      <Hero onNav={onNav} />

      <section className="section section-gray" style={{ paddingTop: 64, paddingBottom: 56 }}>
        <KpiStrip />
      </section>

      <section className="section">
        <div className="container">
          <div className="section-head">
            <span className="eyebrow">Vista rápida del sistema</span>
            <h2>Tres lentes sobre el agro colombiano</h2>
            <p>Mapa territorial, evolución de rendimiento y semáforo de riesgo. Un panorama de un vistazo, antes de profundizar en cada dashboard.</p>
          </div>

          <div className="qv-grid">
            <div className="card">
              <div className="card-head">
                <div>
                  <h3>Mapa territorial</h3>
                  <div className="panel-sub">Estado por municipio · Q2 2026</div>
                </div>
                <span className="src-badge">dim_municipio</span>
              </div>
              <div className="card-body">
                <div className="map-frame">
                  <ColombiaMap puntos={puntos} height={260} />
                </div>
                <div className="legend-row">
                  <span className="legend-dot">Estable</span>
                  <span className="legend-dot amber">Vigilancia</span>
                  <span className="legend-dot red">Alerta</span>
                </div>
              </div>
            </div>

            <div className="card">
              <div className="card-head">
                <div>
                  <h3>Rendimiento histórico</h3>
                  <div className="panel-sub">Maíz · t/ha · 2015–2025</div>
                </div>
                <span className="src-badge">pred_rendimiento</span>
              </div>
              <div className="card-body">
                <div className="chart-frame">
                  <Sparkline height={200} />
                </div>
                <div className="chart-metrics">
                  <div className="chart-metric"><div className="v">4.8</div><div className="l">t/ha prom.</div></div>
                  <div className="chart-metric"><div className="v" style={{ color: "var(--green-700)" }}>+12%</div><div className="l">vs. 2020</div></div>
                  <div className="chart-metric"><div className="v">R²=.81</div><div className="l">Validación</div></div>
                </div>
              </div>
            </div>

            <div className="card">
              <div className="card-head">
                <div>
                  <h3>Semáforo de riesgo</h3>
                  <div className="panel-sub">Distribución nacional</div>
                </div>
                <span className="src-badge">pred_alerta</span>
              </div>
              <div className="card-body">
                <div className="risk-row red">
                  <span className="risk-dot red"></span>
                  <div className="risk-info">
                    <div className="lbl">Alerta</div>
                    <div className="desc">Riesgo climático crítico</div>
                    <div className="risk-bar"><span style={{ width: "18%", background: "var(--red-600)" }}></span></div>
                  </div>
                  <div className="risk-pct">18%</div>
                </div>
                <div className="risk-row amber">
                  <span className="risk-dot amber"></span>
                  <div className="risk-info">
                    <div className="lbl">Vigilancia</div>
                    <div className="desc">Anomalías ENSO en monitoreo</div>
                    <div className="risk-bar"><span style={{ width: "31%", background: "var(--amber-600)" }}></span></div>
                  </div>
                  <div className="risk-pct">31%</div>
                </div>
                <div className="risk-row green">
                  <span className="risk-dot green"></span>
                  <div className="risk-info">
                    <div className="lbl">Estable</div>
                    <div className="desc">Pronóstico favorable</div>
                    <div className="risk-bar"><span style={{ width: "51%", background: "var(--green-600)" }}></span></div>
                  </div>
                  <div className="risk-pct">51%</div>
                </div>
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
              <p>Consolidamos series del DANE, IDEAM, UPRA y SIPSA con frecuencia mensual y municipal. Más de 18 años de cobertura histórica armonizada en un star schema único.</p>
            </div>
            <div className="step">
              <div className="step-head">
                <div className="step-num">2</div>
                <span className="step-pill">Capa analítica</span>
              </div>
              <h3>Analítica y modelos</h3>
              <p>Cinco dashboards de Power BI cubren panorama ejecutivo, producción, clima, calidad de datos y modelos. Un ensamble XGBoost predice rendimiento con R² de 0.81.</p>
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
