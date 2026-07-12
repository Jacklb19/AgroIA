"use client";
import { useEffect, useState } from "react";

const DEBOUNCE = 250;

export default function GemeloDigital({ muni, cultivo }) {
  const [lluvia, setLluvia]   = useState(0);
  const [temp,   setTemp]     = useState(0);
  const [enso,   setEnso]     = useState("Neutral");
  const [fert,   setFert]     = useState(0);
  const [data,   setData]     = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!muni || !cultivo) return;
    setLoading(true);
    const t = setTimeout(() => {
      fetch("/api/simular", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({
          muni, cultivo,
          lluvia_pct:       lluvia,
          temp_delta_c:     temp,
          enso,
          fertilizante_pct: fert,
        }),
      })
        .then((r) => r.json())
        .then((d) => setData(d))
        .catch(() => setData(null))
        .finally(() => setLoading(false));
    }, DEBOUNCE);
    return () => clearTimeout(t);
  }, [muni, cultivo, lluvia, temp, enso, fert]);

  if (!muni || !cultivo) return null;

  const sliderProps = (val, set, min, max, step) => ({
    type: "range",
    min, max, step,
    value: val,
    onChange: (e) => set(parseFloat(e.target.value)),
    style: { width: "100%", accentColor: "#1a7a4a" },
  });

  return (
    <div className="card" style={{ marginTop: 22 }}>
      <div className="card-head">
        <div>
          <h3>🔬 Gemelo digital · simulador de escenarios</h3>
          <p>Mueve los sliders para simular cambios climáticos y de manejo. La proyección se recalcula en vivo sobre la línea base XGBoost.</p>
        </div>
        <span className="src-badge">/api/simular</span>
      </div>
      <div className="card-body">
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 18 }}>
          <div>
            <label style={{ fontSize: 12, fontWeight: 600 }}>
              ☔ Lluvia: <span style={{ color: lluvia > 0 ? "#1a7a4a" : lluvia < 0 ? "#dc2626" : "var(--gray-700)" }}>
                {lluvia > 0 ? "+" : ""}{lluvia}%
              </span>
            </label>
            <input {...sliderProps(lluvia, setLluvia, -30, 30, 1)} />
          </div>
          <div>
            <label style={{ fontSize: 12, fontWeight: 600 }}>
              🌡 Temperatura: <span style={{ color: temp > 0 ? "#dc2626" : temp < 0 ? "#1a7a4a" : "var(--gray-700)" }}>
                {temp > 0 ? "+" : ""}{temp}°C
              </span>
            </label>
            <input {...sliderProps(temp, setTemp, -3, 3, 0.5)} />
          </div>
          <div>
            <label style={{ fontSize: 12, fontWeight: 600 }}>🌀 ENSO</label>
            <select value={enso} onChange={(e) => setEnso(e.target.value)} style={{ width: "100%", padding: "6px 8px", borderRadius: 6, border: "1px solid var(--gray-300)" }}>
              <option>Neutral</option>
              <option>El Niño</option>
              <option>La Niña</option>
            </select>
          </div>
          <div>
            <label style={{ fontSize: 12, fontWeight: 600 }}>
              🌱 Fertilización: <span style={{ color: fert > 0 ? "#1a7a4a" : "var(--gray-700)" }}>
                {fert > 0 ? "+" : ""}{fert}%
              </span>
            </label>
            <input {...sliderProps(fert, setFert, 0, 50, 5)} />
          </div>
        </div>

        {data && (
          <div style={{ marginTop: 22, paddingTop: 18, borderTop: "1px solid var(--gray-200)" }}>
            <div style={{ display: "flex", gap: 22, alignItems: "baseline", flexWrap: "wrap" }}>
              <div>
                <div style={{ fontSize: 11, color: "var(--gray-600)", textTransform: "uppercase", letterSpacing: 0.4 }}>Línea base</div>
                <div style={{ fontSize: 24, fontWeight: 700 }}>{data.baseline} <span style={{ fontSize: 13, color: "var(--gray-500)" }}>t/ha</span></div>
              </div>
              <div style={{ fontSize: 22, color: "var(--gray-400)" }}>→</div>
              <div>
                <div style={{ fontSize: 11, color: "var(--blue-700)", textTransform: "uppercase", letterSpacing: 0.4 }}>Proyectado</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: data.delta_t_ha >= 0 ? "#1a7a4a" : "#dc2626" }}>
                  {data.proyectado} <span style={{ fontSize: 13, color: "var(--gray-500)" }}>t/ha</span>
                </div>
              </div>
              <div style={{ marginLeft: "auto", textAlign: "right" }}>
                <div style={{ fontSize: 11, color: "var(--gray-600)", textTransform: "uppercase", letterSpacing: 0.4 }}>Δ vs base</div>
                <div style={{ fontSize: 18, fontWeight: 600, color: data.delta_t_ha >= 0 ? "#1a7a4a" : "#dc2626" }}>
                  {data.delta_t_ha >= 0 ? "+" : ""}{data.delta_t_ha} t/ha · {data.delta_pct >= 0 ? "+" : ""}{data.delta_pct}%
                </div>
              </div>
            </div>

            <div style={{ marginTop: 14 }}>
              {data.contribuciones.map((c) => {
                const max = Math.max(...data.contribuciones.map((x) => Math.abs(x.valor)), 0.001);
                const pct = (Math.abs(c.valor) / max) * 100;
                const positive = c.valor >= 0;
                return (
                  <div key={c.factor} style={{ marginBottom: 8 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 3 }}>
                      <span>{c.factor}</span>
                      <span style={{ fontFamily: "var(--font-mono)", color: positive ? "#1a7a4a" : "#dc2626" }}>
                        {positive ? "+" : ""}{c.valor}
                      </span>
                    </div>
                    <div style={{ height: 5, background: "#e5e7eb", borderRadius: 3, position: "relative", overflow: "hidden" }}>
                      <div style={{
                        position: "absolute",
                        left: positive ? "50%" : `${50 - pct / 2}%`,
                        width: `${pct / 2}%`,
                        height: "100%",
                        background: positive ? "#1a7a4a" : "#dc2626",
                      }} />
                      <div style={{ position: "absolute", left: "50%", top: 0, bottom: 0, width: 1, background: "#94a3b8" }} />
                    </div>
                  </div>
                );
              })}
            </div>

            <div style={{ marginTop: 12, fontSize: 12, color: "var(--gray-700)", fontStyle: "italic" }}>
              {data.interpretacion}
            </div>
            {loading && <div style={{ fontSize: 11, color: "var(--gray-500)", marginTop: 6 }}>Recalculando…</div>}
          </div>
        )}
      </div>
    </div>
  );
}
