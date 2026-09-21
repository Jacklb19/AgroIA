"use client";
import { Icon } from "./icons";
import { useApi } from "@/lib/useApi";

const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString("es-CO"));

export default function Hero({ onNav, compact = false }) {
  const { data } = useApi("/api/impacto");
  const cobertura = data?.produccion_desde && data?.produccion_hasta ? `${data.produccion_desde}–${data.produccion_hasta}` : "—";

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
          <div className="hero-stat"><div className="num">{fmt(data?.municipios_cubiertos)}</div><div className="lbl">Municipios con datos</div></div>
          <div className="hero-stat"><div className="num">{fmt(data?.cultivos_monitoreados)}</div><div className="lbl">Cultivos</div></div>
          <div className="hero-stat"><div className="num">{cobertura}</div><div className="lbl">Cobertura de producción</div></div>
          <div className="hero-stat"><div className="num">XGBoost</div><div className="lbl">Motor predictivo</div></div>
        </div>
      </div>
    </section>
  );
}
