"use client";
import { Icon } from "./icons";
import KpiSpark from "./charts/KpiSpark";

export default function KpiStrip() {
  return (
    <div className="container">
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-meta">
            <div className="kpi-icon"><Icon.map /></div>
            <KpiSpark data={[1080, 1090, 1098, 1105, 1112, 1118, 1122]} />
          </div>
          <div className="kpi-num">1.122</div>
          <div className="kpi-lbl">Municipios cubiertos</div>
          <div className="kpi-delta">↗ +18 este año</div>
        </div>
        <div className="kpi-card amber">
          <div className="kpi-meta">
            <div className="kpi-icon"><Icon.layers /></div>
            <KpiSpark data={[78, 80, 82, 83, 85, 86, 87]} color="#d97706" />
          </div>
          <div className="kpi-num">87</div>
          <div className="kpi-lbl">Cultivos modelados</div>
          <div className="kpi-delta">↗ +5 vs. 2025</div>
        </div>
        <div className="kpi-card blue">
          <div className="kpi-meta">
            <div className="kpi-icon"><Icon.cpu /></div>
            <KpiSpark data={[28, 30, 33, 35, 38, 41, 42.8]} color="#1e4d7b" />
          </div>
          <div className="kpi-num">42.8k</div>
          <div className="kpi-lbl">Predicciones generadas</div>
          <div className="kpi-delta">↗ +34% trimestre</div>
        </div>
        <div className="kpi-card red">
          <div className="kpi-meta">
            <div className="kpi-icon"><Icon.alert /></div>
            <KpiSpark data={[180, 185, 192, 198, 205, 210, 214]} color="#dc2626" />
          </div>
          <div className="kpi-num">214</div>
          <div className="kpi-lbl">Alertas activas</div>
          <div className="kpi-delta">↗ +12 últimas 24h</div>
        </div>
      </div>
    </div>
  );
}
