"use client";
import { Icon } from "./icons";

export default function Hero({ onNav, compact = false }) {
  return (
    <section className={`hero ${compact ? "hero-compact" : ""}`}>
      <div className="container hero-inner">
        <div className="badge-glass">
          <span className="dot"></span>
          Datos abiertos · Colombia 2026
        </div>
        <h1>
          Inteligencia agroclimática<br />
          con <em>datos abiertos</em>
        </h1>
        <p className="lede">
          Plataforma que transforma datos históricos del DANE, IDEAM y UPRA en monitoreo,
          alertas y predicciones aplicables: territorio, clima, rendimiento y riesgo
          para analistas y tomadores de decisión.
        </p>
        {!compact && (
          <div className="hero-actions">
            <button className="btn-primary" onClick={() => onNav("dashboards")}>
              Ver Dashboards <Icon.arrow className="arrow" />
            </button>
            <button className="btn-outline-white" onClick={() => onNav("prediccion")}>
              Consultar Predicción
            </button>
          </div>
        )}
        <div className="hero-stats">
          <div className="hero-stat"><div className="num">1.122</div><div className="lbl">Municipios</div></div>
          <div className="hero-stat"><div className="num">85+</div><div className="lbl">Cultivos</div></div>
          <div className="hero-stat"><div className="num">2007–26</div><div className="lbl">Cobertura</div></div>
          <div className="hero-stat"><div className="num">XGBoost</div><div className="lbl">Motor predictivo</div></div>
        </div>
      </div>
    </section>
  );
}
