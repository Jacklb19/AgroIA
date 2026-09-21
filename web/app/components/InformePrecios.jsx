"use client";
import { useEffect, useState } from "react";
import Variacion from "./Variacion";
import { cop, fechaCorta, fechaLarga, hora } from "@/lib/formatoPrecios";

function ListaMovimientos({ titulo, items, vacio }) {
  return (
    <div className="card">
      <div className="card-head"><div><h3>{titulo}</h3></div></div>
      <div className="card-body informe-lista">
        {items.length === 0 ? <p className="precios-nota">{vacio}</p> : (
          <ol>
            {items.map((f, i) => (
              <li key={i}>
                <span className="informe-prod"><strong>{f.producto}</strong><small>{f.mercado} · {f.departamento}</small></span>
                <span className="informe-precio">{cop(f.precio)}<small>antes {cop(f.anterior)}</small></span>
                <Variacion v={f.var_pct} />
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}

export default function InformePrecios() {
  const [fecha, setFecha] = useState("");            // "" = el más reciente
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);           // "vacio" | "error"
  const [ventana, setVentana] = useState("dia");      // "dia" | "7d"

  useEffect(() => {
    const ctl = new AbortController();
    setError(null);
    fetch(`/api/precios/informe${fecha ? `?fecha=${fecha}` : ""}`, { signal: ctl.signal })
      .then(async (r) => {
        const d = await r.json();
        if (r.status === 404) { setData(d); setError("vacio"); return; }
        if (!r.ok) throw new Error();
        setData(d);
      })
      .catch((e) => { if (e?.name !== "AbortError") setError("error"); });
    return () => ctl.abort();
  }, [fecha]);

  if (error === "error") return <div className="card"><div className="card-body precios-vacio">El informe no está disponible en este momento.</div></div>;
  if (!data) return <div className="precios-vacio">Cargando informe…</div>;
  if (error === "vacio" || !data.informe) {
    return <div className="card"><div className="card-body precios-vacio">Todavía no se ha generado ningún informe diario.</div></div>;
  }

  const inf = data.informe;
  const c = inf.cobertura;
  const sube = ventana === "dia" ? inf.mayores_subidas_dia : inf.mayores_subidas_7d;
  const baja = ventana === "dia" ? inf.mayores_bajadas_dia : inf.mayores_bajadas_7d;
  const etiqueta = ventana === "dia" ? "del día" : "en 7 días";

  return (
    <div className="informe">
      <div className="informe-cabecera">
        <div>
          <h3>Informe de precios · {fechaLarga(data.fecha)}</h3>
          <p className="precios-nota">
            Reportaron {c.series_con_dato} de {c.series_activas} series ({c.mercados_con_dato} de {c.mercados_activos} mercados):
            no todos los mercados reportan todos los productos cada día. Informe generado a las {hora(data.generado_at)}
          </p>
        </div>
        <div className="field">
          <label htmlFor="inf-fecha">Fecha del informe</label>
          <select id="inf-fecha" value={fecha || data.fecha} onChange={(e) => setFecha(e.target.value)}>
            {data.fechas.map((f) => <option key={f} value={f}>{fechaCorta(f)} {f.slice(0, 4)}</option>)}
          </select>
        </div>
      </div>

      <div className="precios-rangos" role="group" aria-label="Ventana de variación">
        <button type="button" className={`range-btn ${ventana === "dia" ? "active" : ""}`} aria-pressed={ventana === "dia"} onClick={() => setVentana("dia")}>Variación diaria</button>
        <button type="button" className={`range-btn ${ventana === "7d" ? "active" : ""}`} aria-pressed={ventana === "7d"} onClick={() => setVentana("7d")}>Variación en 7 días</button>
      </div>

      <div className="informe-grid">
        <ListaMovimientos titulo={`Mayores subidas ${etiqueta}`} items={sube} vacio="Sin subidas para este período." />
        <ListaMovimientos titulo={`Mayores bajadas ${etiqueta}`} items={baja} vacio="Sin bajadas para este período." />
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-head">
          <div>
            <h3>Dónde está más barato y más caro</h3>
            <div className="panel-sub">Brecha entre mercados por producto (mercados que reportaron ese día)</div>
          </div>
        </div>
        <div className="precios-tabla-wrap" style={{ border: "none", boxShadow: "none", borderRadius: 0 }}>
          <table className="precios-tabla">
            <thead><tr><th>Producto</th><th>Más barato</th><th>Más caro</th><th className="num">Mediana</th><th className="num">Brecha</th></tr></thead>
            <tbody>
              {inf.brecha_entre_mercados.map((b) => (
                <tr key={b.producto} style={{ cursor: "default" }}>
                  <td><strong>{b.producto}</strong><small>{b.n_mercados} mercados</small></td>
                  <td>{cop(b.mas_barato.precio)}<small>{b.mas_barato.mercado}</small></td>
                  <td>{cop(b.mas_caro.precio)}<small>{b.mas_caro.mercado}</small></td>
                  <td className="num">{cop(b.mediana)}</td>
                  <td className="num"><strong>{b.brecha_pct != null ? `${Math.round(b.brecha_pct)} %` : "—"}</strong></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="informe-grid" style={{ marginTop: 16 }}>
        <div className="card">
          <div className="card-head"><div><h3>Por departamento</h3><div className="panel-sub">Variación mediana de los precios que reportaron</div></div></div>
          <div className="precios-tabla-wrap" style={{ border: "none", boxShadow: "none", borderRadius: 0 }}>
            <table className="precios-tabla" style={{ minWidth: 0 }}>
              <thead><tr><th>Departamento</th><th className="num">Series</th><th className="num">Δ día</th><th className="num">Δ 7 días</th></tr></thead>
              <tbody>
                {inf.por_departamento.map((d) => (
                  <tr key={d.departamento} style={{ cursor: "default" }}>
                    <td>{d.departamento}<small>{d.suben_dia} suben · {d.bajan_dia} bajan</small></td>
                    <td className="num">{d.series}</td>
                    <td className="num"><Variacion v={d.var_dia_mediana} /></td>
                    <td className="num"><Variacion v={d.var_7d_mediana} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card">
          <div className="card-head"><div><h3>Precios fuera de lo normal</h3><div className="panel-sub">Muy distintos de su promedio de los últimos 30 datos</div></div></div>
          <div className="card-body informe-lista">
            {inf.atipicos.length === 0 ? <p className="precios-nota">Ningún precio se salió de lo normal ese día.</p> : (
              <ol>
                {inf.atipicos.map((a, i) => (
                  <li key={i}>
                    <span className="informe-prod"><strong>{a.producto}</strong><small>{a.mercado} · {a.departamento}</small></span>
                    <span className="informe-precio">{cop(a.precio)}<small>promedio {cop(a.promedio_30d)}</small></span>
                    <span className={a.z > 0 ? "var-up" : "var-down"} title="Desviaciones estándar respecto al promedio">{a.z > 0 ? "▲" : "▼"} {Math.abs(a.z).toLocaleString("es-CO")} σ</span>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
