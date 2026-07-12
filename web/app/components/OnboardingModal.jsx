"use client";
import { useEffect, useState } from "react";

const STORAGE_KEY = "agroia_onboarding_v1";

const PASOS = [
  {
    icono: "🌱",
    titulo: "Bienvenido a AgroIA Colombia",
    desc:   "Plataforma de inteligencia agroclimática que combina datos abiertos de Colombia con XGBoost, IsolationForest y Claude para apoyar decisiones del sector agropecuario.",
  },
  {
    icono: "📊",
    titulo: "Predicciones explicables",
    desc:   "Cada predicción de rendimiento incluye intervalo de confianza al 95% y un panel SHAP que muestra los 3 factores más influyentes. Sin caja negra.",
  },
  {
    icono: "🤖",
    titulo: "Asistente conversacional",
    desc:   "Pregúntale a Claude por voz o texto: 'compara Espinal y Saldaña', 'qué pasa si hay El Niño en Pasto', 'qué sembrar en Manizales'. Tiene 8 herramientas SQL.",
  },
  {
    icono: "🗺️",
    titulo: "Mapa y dashboards en vivo",
    desc:   "Datos reales del star schema sobre cobertura, alertas y anomalías. Si Power BI no carga, activa el modo offline desde la página de Dashboards.",
  },
];

export default function OnboardingModal({ onNav }) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      if (!localStorage.getItem(STORAGE_KEY)) setOpen(true);
    } catch {
      setOpen(true);
    }
  }, []);

  const cerrar = () => {
    try { localStorage.setItem(STORAGE_KEY, "1"); } catch {}
    setOpen(false);
  };

  const lanzarTour = () => {
    cerrar();
    if (onNav) onNav("prediccion");
  };

  if (!open) return null;
  const cur = PASOS[step];
  const last = step === PASOS.length - 1;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="onboarding-title"
      style={{
        position: "fixed", inset: 0, zIndex: 2000,
        display: "flex", alignItems: "center", justifyContent: "center",
        background: "rgba(11,18,32,0.55)",
        padding: 16,
      }}
      onClick={(e) => e.target === e.currentTarget && cerrar()}
    >
      <div style={{
        background: "white", borderRadius: 14, maxWidth: 480, width: "100%",
        padding: "28px 26px", boxShadow: "0 20px 60px rgba(0,0,0,0.18)",
        position: "relative",
      }}>
        <button
          onClick={cerrar}
          aria-label="Cerrar onboarding"
          style={{
            position: "absolute", top: 10, right: 12,
            background: "none", border: "none", fontSize: 22, cursor: "pointer",
            color: "var(--gray-500)", lineHeight: 1,
          }}
        >×</button>

        <div style={{ fontSize: 40, marginBottom: 10 }}>{cur.icono}</div>
        <h2 id="onboarding-title" style={{ margin: 0, fontSize: 22, marginBottom: 8 }}>{cur.titulo}</h2>
        <p style={{ color: "var(--gray-700)", fontSize: 14, lineHeight: 1.55, margin: 0 }}>{cur.desc}</p>

        <div style={{ display: "flex", gap: 6, marginTop: 22 }}>
          {PASOS.map((_, i) => (
            <div
              key={i}
              style={{
                flex: 1, height: 4, borderRadius: 2,
                background: i <= step ? "var(--blue-700)" : "var(--gray-200)",
                transition: "background 0.2s",
              }}
            />
          ))}
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 22, gap: 8 }}>
          <button
            onClick={cerrar}
            style={{
              padding: "10px 14px", border: "1px solid var(--gray-300)",
              background: "white", borderRadius: 8, cursor: "pointer",
              fontSize: 13, color: "var(--gray-700)",
            }}
          >Saltar</button>
          {last ? (
            <button
              onClick={lanzarTour}
              style={{
                padding: "10px 18px", border: "none",
                background: "var(--blue-700)", color: "white",
                borderRadius: 8, cursor: "pointer", fontSize: 13, fontWeight: 600,
              }}
            >Ir a la predicción →</button>
          ) : (
            <button
              onClick={() => setStep((s) => s + 1)}
              style={{
                padding: "10px 18px", border: "none",
                background: "var(--blue-700)", color: "white",
                borderRadius: 8, cursor: "pointer", fontSize: 13, fontWeight: 600,
              }}
            >Siguiente</button>
          )}
        </div>
      </div>
    </div>
  );
}
