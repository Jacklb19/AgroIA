"use client";
import { useState, useEffect, useRef } from "react";
import ConfidenceBar from "./charts/ConfidenceBar";
import GemeloDigital from "./GemeloDigital";
import { Icon } from "./icons";
import { useApi } from "@/lib/useApi";
import { EmptyState, ErrorState, Skeleton } from "./ui/Estados";
import Term from "./ui/Term";
import DataStamp from "./ui/DataStamp";
import InfoPanel from "./ui/InfoPanel";
import Acciones from "./ui/Acciones";

/* Años ofrecidos: los últimos cuatro con datos históricos y el siguiente (si no hay predicción se avisa). */
const ANIO_ACTUAL = new Date().getFullYear();
const ANIOS = Array.from({ length: 6 }, (_, i) => String(ANIO_ACTUAL - 4 + i));

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
    title: "📅 Año de la predicción",
    desc: "Elige el año. El modelo predice el rendimiento anual; si no hay predicción para ese año, verás la más reciente disponible.",
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

const COLUMNAS_PRED = [
  { clave: "municipio", titulo: "Municipio" }, { clave: "cultivo", titulo: "Cultivo" }, { clave: "anio", titulo: "Año" },
  { clave: "yhat", titulo: "Rendimiento esperado t/ha" }, { clave: "low", titulo: "Límite inferior p10 t/ha" },
  { clave: "high", titulo: "Límite superior p90 t/ha" }, { clave: "riesgo", titulo: "Riesgo" },
  { clave: "real", titulo: "Rendimiento real registrado t/ha" }, { clave: "escenario", titulo: "Escenario ENSO/lluvia" },
];

/* ── Panel de resultado ──────────────────────────────────────────────── */
function ResultPanel({ r }) {
  const riskClass = r.risk ? r.risk.toLowerCase() : "";
  const muniName  = r.muni.split(",")[0];
  const sign      = r.hist != null && r.yhat - r.hist >= 0 ? "+" : "";
  const otroAnio  = r.anio != null && String(r.anio) !== String(r.year);
  const mae       = r.modelo?.error_tipico_t_ha;
  return (
    <div className="result-filled fade-in">
      <div className="result-head">
        <div>
          <h4>{r.cultivo}</h4>
          <div className="sub">{r.muni} · predicción del año {r.anio ?? r.year}</div>
        </div>
        {r.risk ? (
          <span className={`badge-risk ${riskClass}`}>
            <Icon.alert /> Riesgo {r.risk}
          </span>
        ) : (
          <span className="badge-risk" title="No hay una alerta climática registrada para este municipio y año">Sin alerta registrada</span>
        )}
      </div>
      {otroAnio && (
        <p className="kpi-sub" role="note">Se pidió {r.year}, pero la predicción más reciente disponible es la de {r.anio}.</p>
      )}

      <div className="result-main">
        <div>
          <div className="result-num">{r.yhat.toFixed(1)}<small><Term id="t/ha" /></small></div>
          <div className="result-lbl">Rendimiento esperado</div>
        </div>
        {r.low != null && r.high != null && (
          <div className="ci-block">
            <div className="ci-title">Rango probable (<Term id="p10-p90">p10–p90</Term>)</div>
            <ConfidenceBar
              low={r.low} mid={r.yhat} high={r.high}
              vmin={Math.max(0, r.low - 0.5)} vmax={r.high + 0.5}
            />
          </div>
        )}
      </div>

      <div className="metrics-3">
        <div className="metric-mini"><div className="v">{r.risk ?? "—"}</div><div className="l">Nivel de riesgo</div></div>
        <div className="metric-mini"><div className="v">{mae != null ? `±${mae}` : "—"}</div><div className="l"><Term id="MAE">Error típico</Term> (t/ha)</div></div>
        <div className="metric-mini"><div className="v">{r.hist != null ? r.hist.toFixed(2) : "—"}</div><div className="l">Rendimiento real ({r.anio})</div></div>
      </div>

      <div className="context-note">
        <span className="lead">Contexto</span>
        El cultivo de <strong>{r.cultivo.toLowerCase()}</strong> en {muniName}
        {r.hist != null
          ? <> tiene un rendimiento predicho que difiere <strong>{sign}{(r.yhat - r.hist).toFixed(2)} t/ha</strong> del rendimiento real registrado ese año.</>
          : <> tiene un rendimiento esperado de <strong>{r.yhat.toFixed(2)} t/ha</strong>.</>
        }
        {" "}El modelo parte del promedio histórico del municipio y el cultivo y lo ajusta con clima, ENSO y precios cuando hay datos.
        {r.escenario?.ajuste_t_ha !== 0 && r.escenario?.nota && (
          <span style={{ display: "block", marginTop: 6, fontSize: 12 }}>
            Escenario {r.escenario.enso}/{r.escenario.lluvia}: {r.escenario.ajuste_t_ha > 0 ? "+" : ""}{r.escenario.ajuste_t_ha} t/ha sobre la predicción del modelo ({r.yhat_modelo} t/ha). {r.escenario.nota}
          </span>
        )}
      </div>

      <DataStamp fuente="pred_rendimiento (modelo XGBoost)" fecha={r.modelo?.entrenado ? `entrenado el ${r.modelo.entrenado}` : null}
                 nota={`predicción de ${r.anio ?? r.year}`} />
      <InfoPanel>
        <p><strong>Rendimiento esperado:</strong> el modelo estima cuánto se desvía este municipio y cultivo de su promedio histórico y lo suma a ese promedio.</p>
        <p><strong>Rango <Term id="p10-p90">p10–p90</Term>:</strong> calibrado con los errores del modelo en años que no vio al entrenarse.</p>
        <p><strong>Escenarios ENSO / lluvia:</strong> son reglas orientativas fijas aplicadas sobre la predicción; no son salidas del modelo.</p>
        <p>Cifras del modelo, comparación con la <Term id="linea-base">línea base</Term> y límites: <a href="#metodologia">Metodología</a> y <a href="#datos">Datos y transparencia</a>.</p>
      </InfoPanel>
      <Acciones
        nombreArchivo={`prediccion-${r.muni.split(",")[0]}-${r.cultivo}`.toLowerCase().replace(/\s+/g, "-")}
        columnas={COLUMNAS_PRED}
        filas={[{
          municipio: r.muni, cultivo: r.cultivo, anio: r.anio ?? r.year, yhat: r.yhat, low: r.low, high: r.high,
          riesgo: r.risk, real: r.hist, escenario: `${r.escenario_enso}/${r.escenario_lluvia}`,
        }]}
      />

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
  const qs = new URLSearchParams({ muni: r.muni, cultivo: r.cultivo });
  if (r.anio != null) qs.set("anio", r.anio);
  const api = useApi(`/api/comparativo?${qs}`);
  const vecinos = api.data?.vecinos ?? [];

  return (
    <div className="compare-table-wrap fade-in">
      <div className="head">
        <div>
          <h3>Comparativo regional</h3>
          <p>Otros municipios del mismo departamento con predicción de {r.cultivo.toLowerCase()} en {r.anio ?? "el mismo año"}.</p>
        </div>
        <span className="src-badge">pred_rendimiento · mismo departamento</span>
      </div>
      {api.status === "loading" && !api.data && <Skeleton />}
      {api.status === "error" && <ErrorState texto="El comparativo no está disponible en este momento." onReintentar={api.recargar} />}
      {api.status === "ok" && vecinos.length === 0 && (
        <EmptyState titulo="Sin municipios para comparar" texto="No hay otros municipios de este departamento con predicción para este cultivo." />
      )}
      {vecinos.length > 0 && (
        <table className="compare-table">
          <thead>
            <tr><th>Municipio</th><th>Rendimiento predicho</th><th>Riesgo</th><th>vs. real registrado</th></tr>
          </thead>
          <tbody>
            {vecinos.map((n) => (
              <tr key={n.municipio}>
                <td><strong>{n.municipio}</strong></td>
                <td className="num">{n.yhat.toFixed(1)} <span className="muted" style={{ fontSize: 11 }}>t/ha</span></td>
                <td>{n.riesgo ? <span className={`badge-risk ${n.riesgo.toLowerCase()}`}>{n.riesgo}</span> : <span className="muted">—</span>}</td>
                <td className={n.vs_historico_pct == null ? "num" : n.vs_historico_pct >= 0 ? "pos num" : "neg num"}>
                  {n.vs_historico_pct == null ? "—" : `${n.vs_historico_pct >= 0 ? "+" : ""}${n.vs_historico_pct.toFixed(1)}%`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

/* ── Página principal ────────────────────────────────────────────────── */
const ENSO_VALIDOS = ["Neutral", "El Niño", "La Niña"];
const LLUVIA_VALIDAS = ["Normal", "Déficit", "Exceso"];

/* La consulta vive en la URL (#prediccion?m=Pasto&c=Papa&y=2026&enso=El%20Niño&run=1): un enlace reproduce
   la misma vista, con el resultado ya calculado si run=1. */
export default function PagePrediccion({ ruta }) {
  const { params, setParams } = ruta;
  const inicial = useRef({
    m: params.get("m") || "", c: params.get("c") || "", y: params.get("y"), enso: params.get("enso"),
    lluvia: params.get("lluvia"), run: params.get("run") === "1",
  }).current;                       // solo se lee al abrir la página

  const [municipios, setMunicipios] = useState([]);
  const [cultivos,   setCultivos]   = useState([]);
  const [muni,       setMuni]       = useState("");
  const [cultivo,    setCultivo]    = useState("");
  const yearInicial   = ANIOS.includes(inicial.y) ? inicial.y : "2026";
  const ensoInicial   = ENSO_VALIDOS.includes(inicial.enso) ? inicial.enso : "Neutral";
  const lluviaInicial = LLUVIA_VALIDAS.includes(inicial.lluvia) ? inicial.lluvia : "Normal";
  const [year,       setYear]       = useState(yearInicial);
  const [enso,       setEnso]       = useState(ensoInicial);
  const [lluvia,     setLluvia]     = useState(lluviaInicial);
  const [consultado, setConsultado] = useState(false);
  const [listo,      setListo]      = useState(false);   // catálogos cargados: desde aquí los campos se reflejan en la URL
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

  const [catalogoError, setCatalogoError] = useState(false);

  /* Listas reales de municipios y cultivos con producción. Si fallan, se avisa: no hay listas de respaldo. */
  useEffect(() => {
    const cargar = (url, guardar, elegir, deseado) =>
      fetch(url)
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
        .then((data) => {
          const list = Array.isArray(data) ? data : [];
          guardar(list);
          if (list.length) elegir(list.includes(deseado) ? deseado : list[0]);   // el valor del enlace, si existe
          return list.includes(deseado) ? deseado : list[0];
        })
        .catch(() => { setCatalogoError(true); return null; });
    Promise.all([
      cargar("/api/municipios", setMunicipios, setMuni, inicial.m),
      cargar("/api/cultivos", setCultivos, setCultivo, inicial.c),
    ]).then(([m, c]) => {
      setListo(true);
      if (inicial.run && m && c && inicial.m === m && inicial.c === c) consultar({ muni: m, cultivo: c, year: yearInicial, enso: ensoInicial, lluvia: lluviaInicial });
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* Refleja los campos en la URL (reemplaza, no llena el historial). run=1 solo mientras haya un resultado vigente. */
  useEffect(() => {
    if (!listo) return;
    setParams({
      m: muni, c: cultivo, y: year,
      enso: enso === "Neutral" ? "" : enso, lluvia: lluvia === "Normal" ? "" : lluvia,
      run: consultado ? "1" : "",
    });
  }, [listo, muni, cultivo, year, enso, lluvia, consultado, setParams]);

  const cambia = (setter) => (e) => { setter(e.target.value); setConsultado(false); };

  const onSubmit = (e) => { e.preventDefault(); consultar({ muni, cultivo, year, enso, lluvia }); };

  const consultar = async ({ muni, cultivo, year, enso, lluvia }) => {
    setLoading(true); setResult(null); setConsultado(true);
    try {
      const res = await fetch("/api/prediccion", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ muni, cultivo, year, enso, lluvia }),
      });
      const data = await res.json().catch(() => null);
      if (res.status === 404) setResult({ sinDatos: true, muni, cultivo, mensaje: data?.mensaje });
      else if (!res.ok || !data) setResult({ error: true });
      else setResult({ ...data, escenario_enso: enso, escenario_lluvia: lluvia });
    } catch {
      setResult({ error: true });      // sin conexión: se avisa, no se calcula un valor de reemplazo
    } finally {
      setLoading(false);
    }
  };

  const hayResultado = result && !result.error && !result.sinDatos;

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
                  <label htmlFor="pred-muni">Municipio</label>
                  <select id="pred-muni" value={muni} onChange={cambia(setMuni)}>
                    {municipios.map((m) => <option key={m}>{m}</option>)}
                  </select>
                  <ClimaActualWidget muni={muni} />
                </div>
              </div>

              <div className="form-row" ref={cultivoRef}>
                <div className="field">
                  <label htmlFor="pred-cultivo">Cultivo</label>
                  <select id="pred-cultivo" value={cultivo} onChange={cambia(setCultivo)}>
                    {cultivos.map((c) => <option key={c}>{c}</option>)}
                  </select>
                </div>
              </div>

              <div className="form-row" ref={periodoRef}>
                <div className="field">
                  <label htmlFor="pred-anio">Año de la predicción</label>
                  <select id="pred-anio" value={year} onChange={cambia(setYear)}>
                    {ANIOS.map((a) => <option key={a}>{a}</option>)}
                  </select>
                  <div className="kpi-sub">El modelo predice el rendimiento anual. Si no hay predicción para ese año, se muestra la más reciente disponible.</div>
                </div>
              </div>

              <div className="adv" ref={escenariosRef}>
                <div className="adv-title">Escenarios avanzados</div>
                <div className="form-row cols2" style={{ marginBottom: 0 }}>
                  <div className="field">
                    <label htmlFor="pred-enso"><Term id="ENSO" /></label>
                    <select id="pred-enso" value={enso} onChange={cambia(setEnso)}>
                      <option>Neutral</option><option>El Niño</option><option>La Niña</option>
                    </select>
                  </div>
                  <div className="field">
                    <label htmlFor="pred-lluvia">Régimen lluvia</label>
                    <select id="pred-lluvia" value={lluvia} onChange={cambia(setLluvia)}>
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
                  <div className="sub">Consultando la predicción guardada del modelo.</div>
                </div>
              )}
              {result?.error && !loading && <ErrorState texto="La predicción no está disponible en este momento. Intenta de nuevo en unos minutos." />}
              {result?.sinDatos && !loading && (
                <EmptyState titulo="Sin predicción para esta combinación"
                  texto={result.mensaje || "El modelo no tiene predicciones para ese municipio y cultivo."} />
              )}
              {hayResultado && !loading && <ResultPanel r={result} />}
            </div>
          </div>

          {catalogoError && (
            <div style={{ marginTop: 16 }}>
              <ErrorState texto="No se pudieron cargar las listas de municipios y cultivos. Recarga la página o inténtalo más tarde." />
            </div>
          )}

          {hayResultado && !loading && <CompareTable r={result} />}
          {hayResultado && !loading && (
            <RecomendacionPanel
              muni={result.muni}
              cultivo={result.cultivo}
              enso={result.escenario_enso || "Neutral"}
              lluvia={result.escenario_lluvia || "Normal"}
            />
          )}
          {hayResultado && !loading && <GemeloDigital muni={result.muni} cultivo={result.cultivo} />}
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
        {data.aviso && <p className="kpi-sub" role="note" style={{ marginTop: 10 }}>ℹ️ {data.aviso}</p>}
      </div>
    </div>
  );
}
