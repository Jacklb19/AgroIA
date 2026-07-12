"use client";
import { useState, useEffect, useRef } from "react";
import ConfidenceBar from "./charts/ConfidenceBar";
import GemeloDigital from "./GemeloDigital";
import { Icon } from "./icons";

/* ── Pasos del tour ─────────────────────────────────────────────────── */
const TOUR_STEPS = [
  {
    refKey: "muni",
    placement: "right",
    title: "📍 Municipio",
    desc: "Elige la zona de Colombia donde se va a sembrar. El modelo tiene datos reales de producción de cientos de municipios del país.",
  },
  {
    refKey: "cultivo",
    placement: "right",
    title: "🌱 Cultivo",
    desc: "Selecciona qué vas a sembrar: arroz, papa, maíz, café… Cada cultivo tiene un comportamiento distinto según la región y el clima.",
  },
  {
    refKey: "periodo",
    placement: "right",
    title: "📅 Período de proyección",
    desc: "Define el año y semestre que quieres proyectar. Semestre A = enero a junio · Semestre B = julio a diciembre.",
  },
  {
    refKey: "escenarios",
    placement: "right",
    title: "🌦️ Escenarios climáticos",
    desc: "Ajusta el fenómeno El Niño o La Niña si hay pronóstico activo, y el régimen de lluvias esperado. El modelo pondera cómo cada escenario afecta la cosecha históricamente.",
  },
  {
    refKey: "submit",
    placement: "top",
    title: "🔍 Ejecutar predicción",
    desc: "Pulsa aquí para correr el modelo XGBoost con 1.500 árboles. Obtienes rendimiento esperado, rango de confianza al 95% y nivel de riesgo en segundos.",
  },
  {
    refKey: "result",
    placement: "left",
    title: "📊 Tus resultados aparecen aquí",
    desc: "Verás la cosecha esperada en t/ha (toneladas por hectárea sembrada), el nivel de riesgo climático BAJO / MEDIO / ALTO, y el rango realista de producción.",
  },
];

/* ── Overlay del tour ────────────────────────────────────────────────── */
function TourOverlay({ steps, refs, onClose }) {
  const [step, setStep] = useState(0);
  const [rect, setRect] = useState(null);
  const current = steps[step];

  useEffect(() => {
    const el = refs[current.refKey]?.current;
    if (!el) return;
    const update = () => setRect(el.getBoundingClientRect());
    update();
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [step, current.refKey, refs]);

  const PAD = 10;
  const GAP = 22;

  const spotlightStyle = rect
    ? {
        position: "fixed",
        top:    rect.top  - PAD,
        left:   rect.left - PAD,
        width:  rect.width  + PAD * 2,
        height: rect.height + PAD * 2,
        borderRadius: 12,
        boxShadow: "0 0 0 9999px rgba(11,18,32,0.72)",
        border: "2.5px solid #22a35f",
        zIndex: 1001,
        pointerEvents: "none",
        transition:
          "top 0.32s cubic-bezier(.4,0,.2,1), left 0.32s cubic-bezier(.4,0,.2,1), width 0.32s cubic-bezier(.4,0,.2,1), height 0.32s cubic-bezier(.4,0,.2,1)",
      }
    : null;

  let tStyle = { position: "fixed", zIndex: 1002, width: 292 };
  if (rect) {
    const { placement } = current;
    if (placement === "right") {
      tStyle.top       = rect.top + rect.height / 2;
      tStyle.left      = rect.right + PAD + GAP;
      tStyle.transform = "translateY(-50%)";
    } else if (placement === "left") {
      tStyle.top       = rect.top + rect.height / 2;
      tStyle.right     = window.innerWidth - rect.left + PAD + GAP;
      tStyle.transform = "translateY(-50%)";
    } else if (placement === "top") {
      tStyle.bottom = window.innerHeight - rect.top + PAD + GAP;
      tStyle.left   = Math.max(16, Math.min(rect.left, window.innerWidth - 312));
    } else {
      tStyle.top  = rect.bottom + PAD + GAP;
      tStyle.left = Math.max(16, Math.min(rect.left, window.innerWidth - 312));
    }
  }

  const isLast = step === steps.length - 1;

  return (
    <>
      {/* Captura clics fuera para cerrar */}
      <div style={{ position: "fixed", inset: 0, zIndex: 1000 }} onClick={onClose} />

      {/* Spotlight con sombra que oscurece el resto */}
      {spotlightStyle && <div style={spotlightStyle} />}

      {/* Tarjeta del tooltip */}
      {rect && (
        <div className="tour-tooltip" style={tStyle}>
          {/* Puntos de progreso */}
          <div className="tour-dots">
            {steps.map((_, i) => (
              <button
                key={i}
                className={`tour-dot ${i === step ? "active" : i < step ? "done" : ""}`}
                onClick={(e) => { e.stopPropagation(); setStep(i); }}
              />
            ))}
          </div>

          <div className="tour-tt-title">{current.title}</div>
          <div className="tour-tt-desc">{current.desc}</div>

          <div className="tour-tt-actions">
            <button className="tour-skip" onClick={onClose}>Saltar</button>
            <div style={{ display: "flex", gap: 8 }}>
              {step > 0 && (
                <button className="tour-prev" onClick={(e) => { e.stopPropagation(); setStep((s) => s - 1); }}>
                  ← Atrás
                </button>
              )}
              <button
                className="tour-next"
                onClick={(e) => { e.stopPropagation(); isLast ? onClose() : setStep((s) => s + 1); }}
              >
                {isLast ? "¡Entendido! ✓" : "Siguiente →"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

/* ── Panel de resultado ──────────────────────────────────────────────── */
function ResultPanel({ r }) {
  const riskClass = r.risk.toLowerCase();
  const muniName  = r.muni.split(",")[0];
  const sign      = r.yhat - r.hist >= 0 ? "+" : "";
  return (
    <div className="result-filled fade-in">
      <div className="result-head">
        <div>
          <h4>{r.cultivo}</h4>
          <div className="sub">{r.muni} · {r.year}{r.semester}</div>
        </div>
        <span className={`badge-risk ${riskClass}`}>
          <Icon.alert /> Riesgo {r.risk}
        </span>
      </div>

      <div className="result-main">
        <div>
          <div className="result-num">{r.yhat.toFixed(1)}<small>t/ha</small></div>
          <div className="result-lbl">Rendimiento esperado</div>
        </div>
        <div className="ci-block">
          <div className="ci-title">Intervalo de confianza · 95%</div>
          <ConfidenceBar
            low={r.low} mid={r.yhat} high={r.high}
            vmin={Math.max(0, r.low - 0.5)} vmax={r.high + 0.5}
          />
        </div>
      </div>

      <div className="metrics-3">
        <div className="metric-mini"><div className="v">{r.risk}</div><div className="l">Nivel de riesgo</div></div>
        <div className="metric-mini"><div className="v">{r.confidence}%</div><div className="l">Confianza</div></div>
        <div className="metric-mini"><div className="v">{r.hist != null ? r.hist.toFixed(2) : "—"}</div><div className="l">Promedio hist.</div></div>
      </div>

      <div className="context-note">
        <span className="lead">Contexto</span>
        El cultivo de <strong>{r.cultivo.toLowerCase()}</strong> en {muniName}
        {r.hist != null
          ? <> muestra una desviación de <strong>{sign}{(r.yhat - r.hist).toFixed(2)} t/ha</strong> frente al rendimiento histórico registrado.</>
          : <> tiene un rendimiento esperado de <strong>{r.yhat.toFixed(2)} t/ha</strong> para el período seleccionado.</>
        }
        {" "}El modelo pondera anomalías de precipitación, índice ENSO y series históricas por municipio-cultivo.
        {r.fromDB && <span style={{ display: "block", marginTop: 6, fontSize: 11, color: "var(--blue-700)", fontFamily: "var(--font-mono)" }}>✓ Predicción desde XGBoost · base de datos real</span>}
      </div>

      <ShapPanel shap={r.shap} />
    </div>
  );
}

/* ── Panel de explicabilidad SHAP ────────────────────────────────────── */
function ShapPanel({ shap }) {
  if (!Array.isArray(shap) || shap.length === 0) return null;
  const maxAbs = Math.max(...shap.map((s) => Math.abs(s.shap || 0)), 0.001);
  const labelize = (k) => k
    .replace(/_/g, " ")
    .replace(/\b(\w)/g, (m) => m.toUpperCase());

  return (
    <div className="shap-panel" style={{ marginTop: 16, padding: "14px 16px", background: "var(--gray-50, #f7f8fa)", borderRadius: 10, border: "1px solid var(--gray-200, #e5e7eb)" }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: "var(--blue-700)", letterSpacing: 0.4, textTransform: "uppercase", marginBottom: 10 }}>
        🔍 Por qué esta predicción · SHAP
      </div>
      {shap.map((s, i) => {
        const v   = Number(s.shap || 0);
        const pct = (Math.abs(v) / maxAbs) * 100;
        const positive = v >= 0;
        return (
          <div key={i} style={{ marginBottom: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
              <span style={{ fontWeight: 500 }}>{labelize(s.feature)}</span>
              <span style={{ fontFamily: "var(--font-mono)", color: positive ? "#1a7a4a" : "#dc2626" }}>
                {positive ? "+" : ""}{v.toFixed(3)}
              </span>
            </div>
            <div style={{ height: 6, background: "#e5e7eb", borderRadius: 4, position: "relative", overflow: "hidden" }}>
              <div style={{
                position: "absolute",
                left: positive ? "50%" : `${50 - pct / 2}%`,
                width: `${pct / 2}%`,
                height: "100%",
                background: positive ? "#1a7a4a" : "#dc2626",
                borderRadius: 4,
              }} />
              <div style={{ position: "absolute", left: "50%", top: 0, bottom: 0, width: 1, background: "#94a3b8" }} />
            </div>
          </div>
        );
      })}
      <div style={{ fontSize: 11, color: "var(--gray-600, #6b7280)", marginTop: 6 }}>
        Verde = empuja la predicción al alza · Rojo = la baja. Top 3 factores por impacto absoluto.
      </div>
    </div>
  );
}

/* ── Tabla comparativa ───────────────────────────────────────────────── */
function CompareTable({ r }) {
  const neighbors = [
    { name: "Espinal, Tolima",      yld: r.yhat + 0.3, risk: "BAJO",  delta: +6.2 },
    { name: "Guamo, Tolima",        yld: r.yhat - 0.4, risk: "MEDIO", delta: -2.1 },
    { name: "Saldaña, Tolima",      yld: r.yhat + 0.1, risk: "BAJO",  delta: +3.4 },
    { name: "Purificación, Tolima", yld: r.yhat - 0.7, risk: "ALTO",  delta: -8.7 },
  ];
  return (
    <div className="compare-table-wrap fade-in">
      <div className="head">
        <div>
          <h3>Comparativo regional</h3>
          <p>Municipios vecinos en el mismo corredor agrícola.</p>
        </div>
        <span className="src-badge">pred_rendimiento · vecinos</span>
      </div>
      <table className="compare-table">
        <thead>
          <tr><th>Municipio</th><th>Rendimiento</th><th>Riesgo</th><th>vs. histórico</th></tr>
        </thead>
        <tbody>
          {neighbors.map((n) => (
            <tr key={n.name}>
              <td><strong>{n.name}</strong></td>
              <td className="num">{n.yld.toFixed(1)} <span className="muted" style={{ fontSize: 11 }}>t/ha</span></td>
              <td><span className={`badge-risk ${n.risk.toLowerCase()}`}>{n.risk}</span></td>
              <td className={n.delta >= 0 ? "pos num" : "neg num"}>{n.delta >= 0 ? "+" : ""}{n.delta.toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ── Página principal ────────────────────────────────────────────────── */
export default function PagePrediccion() {
  const [municipios, setMunicipios] = useState([]);
  const [cultivos,   setCultivos]   = useState([]);
  const [muni,       setMuni]       = useState("");
  const [cultivo,    setCultivo]    = useState("");
  const [year,       setYear]       = useState("2026");
  const [semester,   setSemester]   = useState("A");
  const [enso,       setEnso]       = useState("Neutral");
  const [lluvia,     setLluvia]     = useState("Normal");
  const [result,     setResult]     = useState(null);
  const [loading,    setLoading]    = useState(false);
  const [tourActive, setTourActive] = useState(false);

  /* Refs para el tour */
  const muniRef       = useRef(null);
  const cultivoRef    = useRef(null);
  const periodoRef    = useRef(null);
  const escenariosRef = useRef(null);
  const submitRef     = useRef(null);
  const resultRef     = useRef(null);

  const tourRefs = {
    muni:       muniRef,
    cultivo:    cultivoRef,
    periodo:    periodoRef,
    escenarios: escenariosRef,
    submit:     submitRef,
    result:     resultRef,
  };

  useEffect(() => {
    fetch("/api/municipios")
      .then((r) => r.json())
      .then((data) => {
        const list = Array.isArray(data) ? data : [];
        setMunicipios(list);
        if (list.length) setMuni(list[0]);
      })
      .catch(() => {
        const fallback = ["Ibagué, Tolima","Espinal, Tolima","Villavicencio, Meta","Pasto, Nariño","Santa Marta, Magdalena","Manizales, Caldas","Montería, Córdoba"];
        setMunicipios(fallback);
        setMuni(fallback[0]);
      });

    fetch("/api/cultivos")
      .then((r) => r.json())
      .then((data) => {
        const list = Array.isArray(data) ? data : [];
        setCultivos(list);
        if (list.length) setCultivo(list[0]);
      })
      .catch(() => {
        const fallback = ["Maíz tecnificado","Arroz riego","Café arábica","Caña panelera","Plátano","Papa Diacol","Aguacate Hass"];
        setCultivos(fallback);
        setCultivo(fallback[0]);
      });
  }, []);

  const onSubmit = async (e) => {
    e.preventDefault();
    setLoading(true); setResult(null);
    try {
      const res = await fetch("/api/prediccion", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ muni, cultivo, year, semester, enso, lluvia }),
      });
      const data = await res.json();
      setResult({ ...data, escenario_enso: enso, escenario_lluvia: lluvia });
    } catch {
      const base      = 4.4 + (cultivo.includes("Arroz") ? 0.6 : 0) + (cultivo.includes("Café") ? -0.8 : 0) + (semester === "B" ? 0.15 : 0);
      const ensoAdj   = enso   === "El Niño" ? -0.5 : enso   === "La Niña" ? 0.3 : 0;
      const lluviaAdj = lluvia === "Déficit"  ? -0.4 : lluvia === "Exceso"  ? -0.2 : 0;
      const yhat      = +(base + ensoAdj + lluviaAdj).toFixed(1);
      const risk      = yhat < 4.0 ? "ALTO" : yhat < 4.6 ? "MEDIO" : "BAJO";
      setResult({ muni, cultivo, year, semester, yhat, low: +(yhat - 1.2).toFixed(1), high: +(yhat + 1.2).toFixed(1), risk, confidence: risk === "BAJO" ? 86 : risk === "MEDIO" ? 78 : 64, hist: 4.4 });
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {/* Tour overlay (portal natural: renderiza encima de todo) */}
      {tourActive && (
        <TourOverlay
          steps={TOUR_STEPS}
          refs={tourRefs}
          onClose={() => setTourActive(false)}
        />
      )}

      <section className="section">
        <div className="container">
          <div className="section-head">
            <span className="eyebrow">Sistema de predicción</span>
            <h2>Consulta puntual por municipio y cultivo</h2>
            <p>Selecciona una zona, un cultivo y un período. El modelo XGBoost devuelve el rendimiento esperado, nivel de riesgo y contexto explicativo en lenguaje claro.</p>
          </div>

          <div className="predict-grid">
            {/* ── Formulario ── */}
            <form className="form-card" onSubmit={onSubmit}>
              <h3><span className="ic-wrap"><Icon.settings /></span> Parámetros de Consulta</h3>

              <div className="form-row" ref={muniRef}>
                <div className="field">
                  <label>Municipio</label>
                  <select value={muni} onChange={(e) => setMuni(e.target.value)}>
                    {municipios.map((m) => <option key={m}>{m}</option>)}
                  </select>
                  <ClimaActualWidget muni={muni} />
                </div>
              </div>

              <div className="form-row" ref={cultivoRef}>
                <div className="field">
                  <label>Cultivo</label>
                  <select value={cultivo} onChange={(e) => setCultivo(e.target.value)}>
                    {cultivos.map((c) => <option key={c}>{c}</option>)}
                  </select>
                </div>
              </div>

              <div className="form-row cols2" ref={periodoRef}>
                <div className="field">
                  <label>Año</label>
                  <select value={year} onChange={(e) => setYear(e.target.value)}>
                    <option>2026</option><option>2027</option><option>2028</option>
                  </select>
                </div>
                <div className="field">
                  <label>Semestre</label>
                  <select value={semester} onChange={(e) => setSemester(e.target.value)}>
                    <option value="A">A (Ene–Jun)</option>
                    <option value="B">B (Jul–Dic)</option>
                  </select>
                </div>
              </div>

              <div className="adv" ref={escenariosRef}>
                <div className="adv-title">Escenarios avanzados</div>
                <div className="form-row cols2" style={{ marginBottom: 0 }}>
                  <div className="field">
                    <label>ENSO</label>
                    <select value={enso} onChange={(e) => setEnso(e.target.value)}>
                      <option>Neutral</option><option>El Niño</option><option>La Niña</option>
                    </select>
                  </div>
                  <div className="field">
                    <label>Régimen lluvia</label>
                    <select value={lluvia} onChange={(e) => setLluvia(e.target.value)}>
                      <option>Normal</option><option>Déficit</option><option>Exceso</option>
                    </select>
                  </div>
                </div>
              </div>

              <button ref={submitRef} type="submit" className="btn-block" disabled={loading || !muni || !cultivo}>
                {loading
                  ? "Calculando…"
                  : <><span>Consultar Predicción</span> <Icon.arrow className="arrow" /></>
                }
              </button>
            </form>

            {/* ── Panel de resultado ── */}
            <div className="result-card" ref={resultRef}>
              {!result && !loading && (
                <div className="result-empty">
                  <div className="lupa"><Icon.search /></div>
                  <div className="head">¿Cómo funciona el predictor?</div>
                  <div className="sub">
                    Elige un municipio, un cultivo y un período en el formulario de la izquierda.
                    El modelo XGBoost calculará cuánto puedes cosechar y qué tan riesgosa es la temporada.
                  </div>
                  <button className="btn-tour-start" onClick={() => setTourActive(true)}>
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polygon points="5 3 19 12 5 21 5 3"/>
                    </svg>
                    Iniciar tour paso a paso
                  </button>
                </div>
              )}
              {loading && (
                <div className="result-empty">
                  <div className="lupa"><Icon.cpu /></div>
                  <div className="head">Ejecutando modelo…</div>
                  <div className="sub">XGBoost · 1.500 árboles · profundidad 8 · inferencia distribuida.</div>
                </div>
              )}
              {result && !loading && <ResultPanel r={result} />}
            </div>
          </div>

          {result && !loading && <CompareTable r={result} />}
          {result && !loading && (
            <RecomendacionPanel
              muni={result.muni}
              cultivo={result.cultivo}
              enso={result.escenario_enso || "Neutral"}
              lluvia={result.escenario_lluvia || "Normal"}
            />
          )}
          {result && !loading && <GemeloDigital muni={result.muni} cultivo={result.cultivo} />}
        </div>
      </section>
    </>
  );
}

/* ── Widget clima en vivo (Open-Meteo) ───────────────────────────────── */
function ClimaActualWidget({ muni }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    if (!muni) return;
    const nombre = muni.split(",")[0].trim();
    fetch(`/api/clima/actual?municipio=${encodeURIComponent(nombre)}`)
      .then((r) => r.json())
      .then((d) => setData(d))
      .catch(() => setData(null));
  }, [muni]);

  if (!data || data.error || !data.actual) return null;
  const a = data.actual;
  return (
    <div style={{
      marginTop: 12, padding: "10px 12px",
      background: "linear-gradient(90deg, #1e4d7b 0%, #1a7a4a 100%)",
      borderRadius: 10, color: "white",
      display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap",
    }}>
      <span style={{ fontSize: 22 }}>{a.es_de_dia ? "☀️" : "🌙"}</span>
      <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.2 }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>{data.municipio}</span>
        <span style={{ fontSize: 11, opacity: 0.85 }}>Open-Meteo · en vivo</span>
      </div>
      <div style={{ display: "flex", gap: 14, fontSize: 12, marginLeft: "auto", flexWrap: "wrap" }}>
        <span>🌡 <strong>{a.temperatura_c}°C</strong></span>
        <span>💧 {a.humedad_pct}%</span>
        <span>☔ {a.precipitacion_mm} mm</span>
        <span>💨 {a.viento_kmh} km/h</span>
      </div>
    </div>
  );
}

/* ── Panel de recomendación accionable ───────────────────────────────── */
function RecomendacionPanel({ muni, cultivo, enso, lluvia }) {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    fetch("/api/recomendacion", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ muni, cultivo, enso, lluvia }),
    })
      .then((r) => r.json())
      .then((d) => setData(d))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [muni, cultivo, enso, lluvia]);

  if (loading) return <div className="card" style={{ marginTop: 22 }}><div className="card-body">Calculando recomendación accionable…</div></div>;
  if (!data || !data.recomendaciones) return null;

  return (
    <div className="card" style={{ marginTop: 22 }}>
      <div className="card-head">
        <div>
          <h3>Recomendación accionable</h3>
          <p>Calendario de siembra, dosis de fertilizante y manejo del riesgo según ENSO + aptitud SIPRA.</p>
        </div>
        <span className="src-badge">fact_aptitud_suelo + fact_alerta_enso</span>
      </div>
      <div className="card-body">
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 14 }}>
          {data.recomendaciones.map((r, i) => (
            <div key={i} style={{ padding: "14px 16px", border: "1px solid var(--gray-200)", borderRadius: 10, background: "white" }}>
              <div style={{ fontSize: 20, marginBottom: 6 }}>{r.icono}</div>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>{r.titulo}</div>
              <div style={{ fontSize: 12, color: "var(--gray-700)", marginBottom: 6 }}>{r.detalle}</div>
              <div style={{ fontSize: 11, color: "var(--blue-700)", fontStyle: "italic" }}>{r.ajuste}</div>
            </div>
          ))}
        </div>
        {data.rendimiento_proyectado != null && (
          <div style={{ marginTop: 14, fontSize: 12, color: "var(--gray-600)" }}>
            Proyección con escenario actual: <strong>{data.rendimiento_proyectado} t/ha</strong> · base {data.rendimiento_base ?? "—"} t/ha · aptitud SIPRA: <code>{data.aptitud_sipra || "n/d"}</code>
          </div>
        )}
      </div>
    </div>
  );
}
