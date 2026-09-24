"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import PriceSpark from "./charts/PriceSpark";
import PriceChart from "./charts/PriceChart";
import Variacion from "./Variacion";
import InformePrecios from "./InformePrecios";
import { cop, fechaCorta, hora } from "@/lib/formatoPrecios";
import DataStamp from "./ui/DataStamp";
import InfoPanel from "./ui/InfoPanel";
import Term from "./ui/Term";
import Acciones from "./ui/Acciones";

const REFRESCO_ESTADO_MS = 5 * 60 * 1000;
const RANGOS = [
  { dias: 30, label: "30 días" },
  { dias: 90, label: "3 meses" },
  { dias: 365, label: "1 año" },
  { dias: 2200, label: "Todo" },
];
const ESTADO_TXT = {
  al_dia:        { clase: "ok",   texto: "Al día" },
  retrasado:     { clase: "warn", texto: "Retrasado" },
  desactualizado:{ clase: "bad",  texto: "Desactualizado" },
  sin_datos:     { clase: "bad",  texto: "Sin datos" },
};

/* ── Estado de los datos ─────────────────────────────────────────────── */
function EstadoDatos({ estado }) {
  const [ahora, setAhora] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setAhora(Date.now()), 30000);
    return () => clearInterval(id);
  }, []);

  if (!estado) return <div className="precios-status"><span className="precios-badge">Verificando datos…</span></div>;
  if (estado.error) {
    return <div className="precios-status"><span className="precios-badge bad">Sin conexión a los datos</span></div>;
  }

  const info = ESTADO_TXT[estado.estado] || ESTADO_TXT.sin_datos;
  const revisado = estado.ultima_revision_at ? Math.max(0, Math.round((ahora - new Date(estado.ultima_revision_at)) / 60000)) : null;
  const proxima = new Date(Math.ceil((ahora + 1) / 3600000) * 3600000).toISOString();

  return (
    <div className="precios-status" role="status">
      <span className={`precios-badge ${info.clase}`}>{info.texto}</span>
      <span>
        Dato más reciente: <strong>{fechaCorta(estado.fecha_dato_max)}</strong>
        {estado.publicado_dane_at && <> · publicado por DANE a las {hora(estado.publicado_dane_at)}</>}
      </span>
      <span className="precios-status-sec">
        {revisado != null ? `Revisado hace ${revisado} min` : "Sin revisiones registradas"} · próxima revisión {hora(proxima)}
      </span>
      <span className="precios-status-sec">
        DANE publica una vez por día hábil; los fines de semana y festivos se muestra el último día hábil.
      </span>
    </div>
  );
}

/* ── Filtros ─────────────────────────────────────────────────────────── */
function Filtros({ listas, filtros, onChange }) {
  if (!listas) return null;
  const mercados = filtros.departamento
    ? listas.mercados.filter((m) => m.departamento === filtros.departamento)
    : listas.mercados;

  const grupos = [...new Set(listas.productos.map((p) => p.grupo || "Otros"))].sort((a, b) => a.localeCompare(b, "es"));

  return (
    <div className="precios-filtros">
      <div className="field">
        <label htmlFor="pf-dep">Departamento</label>
        <select id="pf-dep" value={filtros.departamento}
                onChange={(e) => onChange({ departamento: e.target.value, mercado: "" })}>
          <option value="">Todos los departamentos</option>
          {listas.departamentos.map((d) => <option key={d.id || d.nombre} value={d.nombre}>{d.nombre}</option>)}
        </select>
      </div>
      <div className="field">
        <label htmlFor="pf-prod">Producto</label>
        <select id="pf-prod" value={filtros.producto} onChange={(e) => onChange({ producto: e.target.value })}>
          <option value="">Todos los productos</option>
          {grupos.map((g) => (
            <optgroup key={g} label={g}>
              {listas.productos.filter((p) => (p.grupo || "Otros") === g).map((p) => (
                <option key={p.id} value={p.id}>{p.nombre}</option>
              ))}
            </optgroup>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor="pf-merc">Mercado</label>
        <select id="pf-merc" value={filtros.mercado} onChange={(e) => onChange({ mercado: e.target.value })}>
          <option value="">Todos los mercados</option>
          {mercados.map((m) => <option key={m.id} value={m.id}>{m.nombre}</option>)}
        </select>
      </div>
      <button type="button" className="precios-limpiar"
              onClick={() => onChange({ departamento: "", producto: "", mercado: "" })}
              disabled={!filtros.departamento && !filtros.producto && !filtros.mercado}>
        Limpiar filtros
      </button>
    </div>
  );
}

/* ── Tabla ───────────────────────────────────────────────────────────── */
const COLUMNAS = [
  { clave: "producto",        label: "Producto" },
  { clave: "mercado",         label: "Mercado" },
  { clave: "precio_prom_kg",  label: "Precio/kg", num: true },
  { clave: "var_dia_pct",     label: "Δ día",     num: true },
  { clave: "var_7d_pct",      label: "Δ 7 días",  num: true },
  { clave: "rango",           label: "Mín – máx", num: true, noOrden: true },
  { clave: "spark",           label: "30 días",   noOrden: true },
  { clave: "fecha",           label: "Dato del" },
];

function TablaPrecios({ filas, onSeleccionar }) {
  const [orden, setOrden] = useState({ clave: "producto", asc: true });
  const idFila = (f) => `${f.id_central}:${f.id_producto}`;

  const ordenadas = useMemo(() => {
    const { clave, asc } = orden;
    const signo = asc ? 1 : -1;
    return [...filas].sort((a, b) => {
      const va = a[clave], vb = b[clave];
      if (va == null && vb == null) return 0;
      if (va == null) return 1;            // los vacíos siempre al final
      if (vb == null) return -1;
      const c = typeof va === "number" ? va - vb : String(va).localeCompare(String(vb), "es");
      return c * signo || a.mercado.localeCompare(b.mercado, "es");
    });
  }, [filas, orden]);

  const cambiarOrden = (clave) =>
    setOrden((o) => (o.clave === clave ? { clave, asc: !o.asc } : { clave, asc: clave === "producto" || clave === "mercado" }));

  return (
    <>
    {/* En pantallas angostas la tabla se reemplaza por tarjetas (sin scroll horizontal). */}
    <ul className="precios-cards" aria-label="Precios por mercado">
      {ordenadas.map((f) => (
        <li key={idFila(f)}>
          <button type="button" className={`precio-card ${f.dias_atraso > 5 ? "stale" : ""}`} onClick={() => onSeleccionar(f)}
                  aria-label={`${f.producto} en ${f.mercado}: ${cop(f.precio_prom_kg)} por kilo. Ver historial`}>
            <span className="pc-top">
              <span className="pc-prod"><strong>{f.producto}</strong><small>{f.mercado}{f.departamento ? ` · ${f.departamento}` : ""}</small></span>
              <span className="pc-precio"><strong>{cop(f.precio_prom_kg)}</strong><small>por kilo</small></span>
            </span>
            <span className="pc-vars">
              <span>Δ día <Variacion v={f.var_dia_pct} /></span>
              <span>Δ 7 días <Variacion v={f.var_7d_pct} /></span>
            </span>
            <span className="pc-pie">
              {f.precio_min_kg != null && f.precio_max_kg != null ? `Mín – máx ${cop(f.precio_min_kg)} – ${cop(f.precio_max_kg)} · ` : ""}
              Dato del {fechaCorta(f.fecha)}
              {f.dias_atraso > 5 && <span className="precios-tag">sin dato reciente</span>}
            </span>
          </button>
        </li>
      ))}
    </ul>
    <div className="precios-tabla-wrap">
      <table className="precios-tabla">
        <caption className="sr-only">Precios mayoristas por producto y mercado; cada fila abre su historial.</caption>
        <thead>
          <tr>
            {COLUMNAS.map((c) => (
              <th key={c.clave} className={c.num ? "num" : ""}
                  aria-sort={orden.clave === c.clave ? (orden.asc ? "ascending" : "descending") : undefined}>
                {c.noOrden ? c.label : (
                  <button type="button" onClick={() => cambiarOrden(c.clave)}>
                    {c.label}{orden.clave === c.clave ? (orden.asc ? " ↑" : " ↓") : ""}
                  </button>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ordenadas.map((f) => {
            const desactualizada = f.dias_atraso > 5;
            const abrir = () => onSeleccionar(f);
            return (
              <tr key={`${f.id_central}:${f.id_producto}`} className={desactualizada ? "stale" : ""}
                  tabIndex={0} onClick={abrir} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), abrir())}
                  aria-label={`${f.producto} en ${f.mercado}: ${cop(f.precio_prom_kg)} por kilo. Ver historial`}>
                <td><strong>{f.producto}</strong><small>{f.grupo}</small></td>
                <td>{f.mercado}<small>{f.departamento}</small></td>
                <td className="num precio"><strong>{cop(f.precio_prom_kg)}</strong></td>
                <td className="num"><Variacion v={f.var_dia_pct} /></td>
                <td className="num"><Variacion v={f.var_7d_pct} /></td>
                <td className="num rango">
                  {f.precio_min_kg != null && f.precio_max_kg != null ? `${cop(f.precio_min_kg)} – ${cop(f.precio_max_kg)}` : "—"}
                </td>
                <td><PriceSpark values={f.spark} /></td>
                <td>
                  {fechaCorta(f.fecha)}
                  {desactualizada && <span className="precios-tag" title={`Último dato hace ${f.dias_atraso} días`}>sin dato reciente</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
    </>
  );
}

/* ── Historial y pronóstico ──────────────────────────────────────────── */
function Historial({ sel, onVolver }) {
  const [dias, setDias] = useState(90);
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const ctl = new AbortController();
    setData(null); setError(false);
    fetch(`/api/precios/serie?producto=${sel.id_producto}&mercado=${sel.id_central}&dias=${dias}`, { signal: ctl.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setData)
      .catch((e) => { if (e?.name !== "AbortError") setError(true); });
    return () => ctl.abort();
  }, [sel.id_producto, sel.id_central, dias]);

  const resumen = useMemo(() => {
    const s = data?.serie ?? [];
    if (!s.length) return null;
    const precios = s.map((d) => d.prom);
    const primero = s[0], ultimo = s[s.length - 1];
    return {
      ultimo, primero,
      min: Math.min(...precios), max: Math.max(...precios),
      variacion: primero.prom ? ((ultimo.prom - primero.prom) / primero.prom) * 100 : null,
    };
  }, [data]);

  return (
    <div className="card precios-historial">
      <div className="card-head">
        <div>
          <h3>{sel.producto} · {sel.mercado}</h3>
          <div className="panel-sub">{sel.departamento} · precio mayorista promedio en pesos por kilo</div>
        </div>
        <button type="button" className="precios-limpiar" onClick={onVolver}>← Volver a la tabla</button>
      </div>
      <div className="card-body">
        <div className="precios-rangos" role="group" aria-label="Rango de tiempo">
          {RANGOS.map((r) => (
            <button key={r.dias} type="button" className={`range-btn ${dias === r.dias ? "active" : ""}`}
                    aria-pressed={dias === r.dias} onClick={() => setDias(r.dias)}>{r.label}</button>
          ))}
        </div>

        {error && <div className="precios-vacio">No fue posible cargar el historial.</div>}
        {!error && !data && <div className="precios-vacio">Cargando historial…</div>}
        {data && !resumen && <div className="precios-vacio">No hay datos en este rango para este producto y mercado.</div>}

        {data && resumen && (
          <>
            <div className="precios-stats">
              <div><span>Último dato ({fechaCorta(resumen.ultimo.fecha)})</span><strong>{cop(resumen.ultimo.prom)}</strong></div>
              <div><span>Cambio en el período</span><strong><Variacion v={resumen.variacion} /></strong></div>
              <div><span>Mínimo</span><strong>{cop(resumen.min)}</strong></div>
              <div><span>Máximo</span><strong>{cop(resumen.max)}</strong></div>
            </div>

            <PriceChart serie={data.serie} prediccion={data.prediccion} />

            {data.prediccion.length > 0 ? (
              <div className="precios-tabla-wrap" style={{ marginTop: 16 }}>
                <table className="precios-tabla">
                  <thead><tr><th>Pronóstico</th><th className="num">Precio esperado</th><th className="num">Rango probable (p10–p90)</th><th>Confianza</th></tr></thead>
                  <tbody>
                    {data.prediccion.map((p) => (
                      <tr key={p.fecha}>
                        <td>{fechaCorta(p.fecha)}</td>
                        <td className="num"><strong>{cop(p.precio)}</strong></td>
                        <td className="num rango">{cop(p.p10)} – {cop(p.p90)}</td>
                        <td><span className={`precios-badge ${p.confianza === "alta" ? "ok" : p.confianza === "baja" ? "warn" : ""}`}>{p.confianza}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="precios-nota">El pronóstico para esta combinación todavía no está disponible.</p>
            )}
            {data.prediccion.length > 0 && (
              <p className="precios-nota" style={{ marginTop: 10 }}>
                Los pronósticos son a días hábiles y la banda muestra el rango probable (10 %–90 %).
                {data.calidad_pronostico
                  ? ` En pruebas con datos pasados, el error típico de este producto fue de ${data.calidad_pronostico.error_modelo_pct} % con el modelo y de ${data.calidad_pronostico.error_precio_hoy_pct} % si se supone que el precio de hoy no cambia (${data.calidad_pronostico.mejora_pct >= 0 ? "mejora" : "empeora"} ${Math.abs(data.calidad_pronostico.mejora_pct)} %). Donde la confianza es "baja", se muestra el precio de hoy.`
                  : " Todavía no hay pruebas con datos pasados para este producto."}
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}

/* ── Página ──────────────────────────────────────────────────────────── */
const FILTROS_VACIOS = { departamento: "", producto: "", mercado: "" };

const TABS = ["precios", "historial", "informe"];
const COLUMNAS_CSV = [
  { clave: "producto", titulo: "Producto" }, { clave: "grupo", titulo: "Grupo" },
  { clave: "mercado", titulo: "Mercado" }, { clave: "departamento", titulo: "Departamento" },
  { clave: "precio_prom_kg", titulo: "Precio promedio COP/kg" }, { clave: "precio_min_kg", titulo: "Precio mínimo COP/kg" },
  { clave: "precio_max_kg", titulo: "Precio máximo COP/kg" }, { clave: "var_dia_pct", titulo: "Variación día %" },
  { clave: "var_7d_pct", titulo: "Variación 7 días %" }, { clave: "fecha", titulo: "Fecha del dato" },
];

/* Los filtros, la pestaña y la serie abierta viven en la URL (#precios?dep=…&producto=…&tab=historial&serie=…):
   la vista es un enlace compartible y el botón "atrás" funciona. */
export default function PagePrecios({ ruta }) {
  const { params, setParams } = ruta;
  const filtros = useMemo(() => ({
    departamento: params.get("dep") || "", producto: params.get("producto") || "", mercado: params.get("mercado") || "",
  }), [params]);
  const tabUrl = params.get("tab");
  const tab = TABS.includes(tabUrl) ? tabUrl : "precios";
  const serie = params.get("serie") || "";

  const [listas, setListas] = useState(null);
  const [precios, setPrecios] = useState({ estado: "cargando", filas: [] });
  const [estado, setEstado] = useState(null);
  const [recarga, setRecarga] = useState(0);
  const sel = useMemo(
    () => precios.filas.find((f) => `${f.id_central}:${f.id_producto}` === serie) || null,
    [precios.filas, serie],
  );
  const ultimoCambio = useRef(null);   // datos_actualizados_at visto por última vez

  /* Estado de los datos: al montar, cada 5 min y al volver a la pestaña. Recarga la tabla solo si hubo datos nuevos. */
  useEffect(() => {
    let vivo = true;
    const consultar = async () => {
      try {
        const r = await fetch("/api/precios/estado", { cache: "no-store" });
        const d = await r.json();
        if (!vivo) return;
        const previo = ultimoCambio.current;
        if (previo && d.datos_actualizados_at && previo !== d.datos_actualizados_at) setRecarga((n) => n + 1);
        if (d.datos_actualizados_at) ultimoCambio.current = d.datos_actualizados_at;
        setEstado(d);
      } catch {
        if (vivo) setEstado((previo) => previo ?? { error: true });
      }
    };
    // Se salta el chequeo de visibilidad solo en el refresco periódico/por evento (para no gastar
    // llamadas con la pestaña en segundo plano) — nunca en el fetch inicial: si se hiciera, una
    // pestaña que arranca oculta (prerender, apertura en segundo plano) dejaba el badge en
    // "Verificando datos…" para siempre hasta el próximo intervalo de 5 min o cambio de pestaña.
    consultar();
    const consultarSiVisible = () => { if (document.visibilityState === "visible") consultar(); };
    const id = setInterval(consultarSiVisible, REFRESCO_ESTADO_MS);
    document.addEventListener("visibilitychange", consultarSiVisible);
    return () => { vivo = false; clearInterval(id); document.removeEventListener("visibilitychange", consultarSiVisible); };
  }, []);

  useEffect(() => {
    fetch("/api/precios/filtros").then((r) => (r.ok ? r.json() : Promise.reject())).then(setListas).catch(() => setListas(null));
  }, [recarga]);

  useEffect(() => {
    const ctl = new AbortController();
    const qs = new URLSearchParams();
    if (filtros.departamento) qs.set("departamento", filtros.departamento);
    if (filtros.producto) qs.set("producto", filtros.producto);
    if (filtros.mercado) qs.set("mercado", filtros.mercado);
    setPrecios((p) => ({ ...p, estado: "cargando" }));
    fetch(`/api/precios?${qs}`, { signal: ctl.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d) => setPrecios({ estado: "ok", filas: d.precios }))
      .catch((e) => { if (e?.name !== "AbortError") setPrecios({ estado: "error", filas: [] }); });
    return () => ctl.abort();
  }, [filtros, recarga]);

  const cambiarFiltros = (cambio) => {
    const url = {};
    if ("departamento" in cambio) url.dep = cambio.departamento;
    if ("producto" in cambio) url.producto = cambio.producto;
    if ("mercado" in cambio) url.mercado = cambio.mercado;
    setParams(url);                                       // reemplaza: los filtros no llenan el historial del navegador
  };
  const irATab = (t) => setParams({ tab: t === "precios" ? "" : t, serie: t === "historial" ? serie : "" }, { reemplazar: false });
  const abrirHistorial = (fila) => {
    setParams({ tab: "historial", serie: `${fila.id_central}:${fila.id_producto}` }, { reemplazar: false });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const fechaDatos = estado?.fecha_dato_max || precios.filas[0]?.fecha || null;

  return (
    <section className="section">
      <div className="container">
        <div className="section-head">
          <span className="eyebrow amber">Precios</span>
          <h2>Precios mayoristas por mercado y departamento</h2>
          <p>
            Precio por kilo en las principales centrales de abasto de Colombia, con variación diaria y semanal,
            historial y pronóstico. Son precios <Term id="mayorista">mayoristas</Term>, no de venta al consumidor.
          </p>
        </div>

        <EstadoDatos estado={estado} />

        <div className="tabs" role="tablist">
          <button role="tab" aria-selected={tab === "precios"} className={`tab ${tab === "precios" ? "active" : ""}`} onClick={() => irATab("precios")}>
            Precios de hoy
          </button>
          <button role="tab" aria-selected={tab === "historial"} className={`tab ${tab === "historial" ? "active" : ""}`}
                  onClick={() => irATab("historial")} disabled={!sel}>
            Historial y pronóstico
          </button>
          <button role="tab" aria-selected={tab === "informe"} className={`tab ${tab === "informe" ? "active" : ""}`} onClick={() => irATab("informe")}>
            Informe del día
          </button>
        </div>

        {tab === "precios" && (
          <>
            <Filtros listas={listas} filtros={filtros} onChange={cambiarFiltros} />

            {precios.estado === "error" && (
              <div className="card"><div className="card-body precios-vacio">
                Los precios no están disponibles en este momento. Intenta de nuevo en unos minutos.
              </div></div>
            )}
            {precios.estado === "cargando" && precios.filas.length === 0 && <div className="precios-vacio">Cargando precios…</div>}
            {precios.estado === "ok" && precios.filas.length === 0 && (
              <div className="card"><div className="card-body precios-vacio">
                No hay precios recientes para esa combinación. No todos los mercados reportan todos los productos
                (por ejemplo, la papa negra ya no se reporta en Pasto). Prueba con otro producto o mercado.
              </div></div>
            )}
            {precios.filas.length > 0 && (
              <>
                <div className="precios-barra">
                  <p className="precios-nota" aria-live="polite">
                    {precios.filas.length} {precios.filas.length === 1 ? "serie" : "series"} · toca una fila para ver su historial
                  </p>
                  <Acciones nombreArchivo={`precios-mayoristas-${fechaDatos || "actual"}`} columnas={COLUMNAS_CSV} filas={precios.filas} />
                </div>
                <TablaPrecios filas={precios.filas} onSeleccionar={abrirHistorial} />
              </>
            )}
          </>
        )}

        {tab === "informe" && <InformePrecios key={recarga} />}

        {tab === "historial" && sel && <Historial sel={sel} onVolver={() => irATab("precios")} />}
        {tab === "historial" && !sel && precios.estado === "ok" && (
          <div className="card"><div className="card-body precios-vacio">
            No se encontró esa serie de precios (puede que ya no se reporte). <button type="button" className="precios-limpiar" onClick={() => irATab("precios")}>Volver a los precios</button>
          </div></div>
        )}

        <DataStamp fuente="DANE — SIPSA" fecha={fechaDatos ? fechaCorta(fechaDatos) : null} nota="precios mayoristas por kilo" />
        <InfoPanel>
          <p><strong>Precio:</strong> promedio diario por kilo que reporta el DANE en cada central de abasto (<Term id="SIPSA" />). Los mínimos y máximos no los trae todo mercado.</p>
          <p><strong>Δ día:</strong> cambio frente al dato anterior del mismo producto y mercado. <strong>Δ 7 días:</strong> cambio frente al dato de hace una semana o el más cercano anterior.</p>
          <p><strong>Pronóstico:</strong> se evalúa con datos pasados contra el supuesto «el precio de mañana es el de hoy»; donde el modelo no lo supera, la confianza es «baja» y se muestra el precio de hoy. Ver <a href="#metodologia">Metodología</a>.</p>
          <p><strong>Frescura:</strong> el DANE publica una vez por <Term id="dia-habil">día hábil</Term>; el sistema revisa cada hora si hay dato nuevo.</p>
        </InfoPanel>
      </div>
    </section>
  );
}
