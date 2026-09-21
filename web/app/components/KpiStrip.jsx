"use client";
import { Icon } from "./icons";
import { useApi } from "@/lib/useApi";
import { ErrorState } from "./ui/Estados";
import DataStamp from "./ui/DataStamp";

const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString("es-CO"));

/* KPIs reales desde /api/impacto. Sin tendencias ni variaciones inventadas: cada tarjeta muestra
   solo lo que la base de datos puede respaldar. */
export default function KpiStrip() {
  const api = useApi("/api/impacto");
  const d = api.data;
  const cargando = api.status === "loading" && !d;

  if (api.status === "error") {
    return <div className="container"><ErrorState texto="Los indicadores no están disponibles en este momento." onReintentar={api.recargar} /></div>;
  }

  const valor = (v) => (cargando ? <span className="skel" style={{ display: "inline-block", width: 90, height: 34 }} /> : fmt(v));
  const periodo = d?.produccion_desde && d?.produccion_hasta ? `Producción ${d.produccion_desde}–${d.produccion_hasta}` : "Sin producción cargada";

  return (
    <div className="container">
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-meta"><div className="kpi-icon"><Icon.map /></div></div>
          <div className="kpi-num">{valor(d?.municipios_cubiertos)}</div>
          <div className="kpi-lbl">Municipios con producción registrada</div>
          <div className="kpi-sub">{cargando ? "" : periodo}</div>
        </div>
        <div className="kpi-card amber">
          <div className="kpi-meta"><div className="kpi-icon"><Icon.layers /></div></div>
          <div className="kpi-num">{valor(d?.cultivos_monitoreados)}</div>
          <div className="kpi-lbl">Cultivos con producción registrada</div>
          <div className="kpi-sub">{cargando ? "" : `${fmt(d?.hectareas_cobertura)} ha sembradas acumuladas`}</div>
        </div>
        <div className="kpi-card blue">
          <div className="kpi-meta"><div className="kpi-icon"><Icon.cpu /></div></div>
          <div className="kpi-num">{valor(d?.predicciones_total)}</div>
          <div className="kpi-lbl">Predicciones de rendimiento</div>
          <div className="kpi-sub">{cargando ? "" : d?.modelo_actualizado ? `Modelo entrenado el ${d.modelo_actualizado}` : "Aún sin modelo entrenado"}</div>
        </div>
        <div className="kpi-card red">
          <div className="kpi-meta"><div className="kpi-icon"><Icon.alert /></div></div>
          <div className="kpi-num">{valor(d?.alertas_activas)}</div>
          <div className="kpi-lbl">Alertas activas</div>
          <div className="kpi-sub">{cargando ? "" : `${fmt(d?.alertas_alto_riesgo)} de riesgo alto`}</div>
        </div>
      </div>
      <DataStamp fuente="fact_produccion_agricola · pred_rendimiento · pred_alerta_climatica" nota="calculado en tiempo real" />
    </div>
  );
}
