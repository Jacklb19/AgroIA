"use client";
import { useApi } from "@/lib/useApi";
import { EmptyState, ErrorState, Skeleton } from "./ui/Estados";
import DataStamp from "./ui/DataStamp";
import InfoPanel from "./ui/InfoPanel";
import Term from "./ui/Term";
import Acciones from "./ui/Acciones";

const NOMBRES_ETAPA = {
  pipeline_core:     "ETL de producción y clima",
  pipeline_extended: "ETL extendido (ENSO, insumos, suelos, censo)",
  pipeline_models:   "Entrenamiento de los modelos",
  sipsa_excel:       "Precios SIPSA · boletín diario (Excel)",
  sipsa_soap:        "Precios SIPSA · historial (servicio SOAP)",
  forecast_precio:   "Pronóstico de precios",
};

const ESTADO_GENERAL = {
  ok:           { clase: "ok",   texto: "Todo en orden" },
  con_alertas:  { clase: "warn", texto: "Con alertas de calidad" },
  con_errores:  { clase: "bad",  texto: "Alguna etapa falló en su última corrida" },
  sin_datos:    { clase: "bad",  texto: "Aún no hay ejecuciones registradas" },
};

const fmt = new Intl.DateTimeFormat("es-CO", { dateStyle: "medium", timeStyle: "short", timeZone: "America/Bogota" });
const cuando = (iso) => (iso ? fmt.format(new Date(iso)) : "—");
const dia = (iso) => (iso ? String(iso).slice(0, 10) : "—");
const nf = new Intl.NumberFormat("es-CO");

function Bloque({ id, titulo, sub, children }) {
  return (
    <section className="datos-bloque card" aria-labelledby={id}>
      <div className="card-body">
        <h3 id={id}>{titulo}</h3>
        {sub && <p className="panel-sub">{sub}</p>}
        {children}
      </div>
    </section>
  );
}

function Cargando({ api, children }) {
  if (api.status === "loading" && !api.data) return <Skeleton />;
  if (api.status === "error") return <ErrorState onReintentar={api.recargar} />;
  return children;
}

/* ── 1. Estado del sistema ─────────────────────────────────────────────── */
function EstadoSistema({ api }) {
  const d = api.data;
  return (
    <Bloque id="d-estado" titulo="Estado del sistema" sub="Última corrida de cada proceso automático. Se actualiza solo.">
      <Cargando api={api}>
        {d && (
          <>
            <p><span className={`precios-badge ${(ESTADO_GENERAL[d.estado] || ESTADO_GENERAL.sin_datos).clase}`}>
              {(ESTADO_GENERAL[d.estado] || ESTADO_GENERAL.sin_datos).texto}
            </span></p>
            {d.fuentes.length === 0 ? (
              <EmptyState titulo="Sin ejecuciones registradas" texto="Todavía no se ha corrido el pipeline en esta base de datos (python run_pipeline.py --mode all --once)." />
            ) : (
              <div className="tabla-scroll">
                <table className="tabla-simple">
                  <caption className="sr-only">Última ejecución de cada proceso</caption>
                  <thead><tr><th>Proceso</th><th>Última revisión</th><th>Última carga correcta</th><th>Dato más reciente</th><th>Estado</th></tr></thead>
                  <tbody>
                    {d.fuentes.map((f) => (
                      <tr key={f.fuente}>
                        <td>{NOMBRES_ETAPA[f.fuente] || f.fuente}</td>
                        <td>{cuando(f.ultima_revision)}</td>
                        <td>{cuando(f.ultima_ok)}</td>
                        <td>{dia(f.fecha_dato_max)}</td>
                        <td>
                          <span className={`precios-badge ${f.ultimo_estado === "error" ? "bad" : f.ultimo_estado === "ok" ? "ok" : "warn"}`}>
                            {f.ultimo_estado === "ok" ? "Correcta" : f.ultimo_estado === "error" ? "Falló" : f.ultimo_estado === "sin_cambios" ? "Sin cambios" : "En curso"}
                          </span>
                          {f.errores_24h > 0 && <small> · {f.errores_24h} fallo(s) en 24 h</small>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <DataStamp fuente="ingest_run (bitácora de ejecuciones)" fecha={d.migraciones?.ultima ? cuando(d.migraciones.ultima) : null}
                       nota={d.migraciones ? `${d.migraciones.n} migraciones de esquema aplicadas` : null} />
          </>
        )}
      </Cargando>
    </Bloque>
  );
}

/* ── 2. Catálogo de fuentes ────────────────────────────────────────────── */
const COLUMNAS_CATALOGO = [
  { clave: "titulo", titulo: "Fuente" }, { clave: "entidad", titulo: "Entidad" }, { clave: "tabla", titulo: "Tabla" },
  { clave: "filas", titulo: "Filas" }, { clave: "uri", titulo: "Enlace" }, { clave: "nota", titulo: "Nota" },
];

function Catalogo({ api }) {
  const lista = Array.isArray(api.data) ? api.data : [];
  return (
    <Bloque id="d-fuentes" titulo="De dónde salen los datos" sub="Cada fuente con su entidad, la tabla donde se guarda y cuántas filas hay cargadas hoy.">
      <Cargando api={api}>
        <Acciones nombreArchivo="fuentes-de-datos" columnas={COLUMNAS_CATALOGO} filas={lista} />
        <div className="tabla-scroll">
          <table className="tabla-simple">
            <caption className="sr-only">Fuentes de datos y filas cargadas</caption>
            <thead><tr><th>Fuente</th><th>Entidad</th><th className="num">Filas cargadas</th></tr></thead>
            <tbody>
              {lista.map((f) => (
                <tr key={f.id}>
                  <td>
                    <a href={f.uri} target="_blank" rel="noopener noreferrer">{f.titulo}</a>
                    <small><code>{f.tabla}</code>{f.nota ? ` · ${f.nota}` : ""}</small>
                  </td>
                  <td>{f.entidad}</td>
                  <td className="num">{f.filas == null ? <span className="muted">No cargada</span> : f.filas === 0 ? <span className="muted">Vacía</span> : nf.format(f.filas)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <DataStamp fuente="conteo directo de tablas" nota="una fuente 'No cargada' no está integrada todavía" />
      </Cargando>
    </Bloque>
  );
}

/* ── 3. Calidad de los datos ───────────────────────────────────────────── */
function Calidad({ api }) {
  const d = api.data;
  return (
    <Bloque id="d-calidad" titulo="Calidad de los datos" sub="Controles automáticos después de cada carga y completitud de cada fuente al extraerla.">
      <Cargando api={api}>
        {d && (d.indicadores.length === 0 && d.reportes.length === 0 ? (
          <EmptyState titulo="Sin reportes de calidad" texto={d.mensaje || "Aún no se ha corrido el pipeline."} />
        ) : (
          <>
            {d.indicadores.length > 0 && (
              <div className="tabla-scroll">
                <table className="tabla-simple">
                  <caption className="sr-only">Controles de calidad</caption>
                  <thead><tr><th>Control</th><th className="num">Valor</th><th>Resultado</th></tr></thead>
                  <tbody>
                    {d.indicadores.map((i) => (
                      <tr key={i.indicador}>
                        <td>{i.descripcion}</td>
                        <td className="num">{i.valor == null ? "—" : nf.format(Math.round(i.valor * 100) / 100)}</td>
                        <td><span className={`precios-badge ${i.estado === "OK" ? "ok" : i.estado === "ALERTA" ? "bad" : "warn"}`}>
                          {i.estado === "OK" ? "Correcto" : i.estado === "ALERTA" ? "En alerta" : "Sin datos"}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {d.reportes.length > 0 && (
              <>
                <h4 className="datos-sub">Completitud por fuente al extraer</h4>
                <div className="tabla-scroll">
                  <table className="tabla-simple">
                    <caption className="sr-only">Completitud de cada fuente</caption>
                    <thead><tr><th>Fuente</th><th className="num">Filas</th><th className="num">Completitud media</th><th>Columnas incompletas (&lt; 80 %)</th></tr></thead>
                    <tbody>
                      {d.reportes.map((r) => (
                        <tr key={r.fuente}>
                          <td>{r.fuente}</td>
                          <td className="num">{r.filas == null ? "—" : nf.format(r.filas)}</td>
                          <td className="num">{r.completitud_media} %</td>
                          <td>{r.columnas_bajas.length ? r.columnas_bajas.map((c) => `${c.col} (${c.completitud} %)`).join(", ") : "Ninguna"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </>
        ))}
        <DataStamp fuente="quality_check_run · extraction_report" />
      </Cargando>
    </Bloque>
  );
}

/* ── 4. Ficha del modelo ───────────────────────────────────────────────── */
function veredicto(m) {
  if (m.mejora_mae_vs_base_pct == null) return null;
  if (m.mejora_mae_vs_base_pct < 0) return "El modelo NO supera a la línea base en el año de prueba: úsalo con mucha cautela.";
  if (m.mejora_mae_vs_base_pct < 5) return `El modelo supera a la línea base por poco (${m.mejora_mae_vs_base_pct} %): úsalo como orientación, no como cifra exacta.`;
  return `El modelo reduce el error de la línea base en ${m.mejora_mae_vs_base_pct} %.`;
}

function FichaModelo({ api }) {
  const d = api.data;
  const r = d?.rendimiento;
  return (
    <Bloque id="d-modelo" titulo="Ficha del modelo" sub="Cómo se comporta el modelo con datos que no vio al entrenarse. Cifras leídas de la base de datos, no escritas a mano.">
      <Cargando api={api}>
        {d && !r && <EmptyState titulo="Modelo sin entrenar" texto="Todavía no hay un modelo de rendimiento activo en esta base de datos." />}
        {r && (
          <>
            <h4 className="datos-sub">Rendimiento de cultivos (t/ha)</h4>
            <dl className="datos-metricas">
              <div><dt>Año de prueba (no usado para entrenar)</dt><dd>{r.anio_corte ?? "—"}</dd></div>
              <div><dt>Observaciones de prueba</dt><dd>{r.n_test != null ? nf.format(r.n_test) : "—"}</dd></div>
              <div><dt><Term id="MAE">Error medio (MAE)</Term> del modelo</dt><dd>{r.mae_t_ha ?? "—"} <small>t/ha</small></dd></div>
              <div><dt>Error medio de la <Term id="linea-base">línea base</Term></dt><dd>{r.linea_base?.mae_t_ha ?? "—"} <small>t/ha</small></dd></div>
              <div><dt>Mejora frente a la línea base</dt><dd>{r.mejora_mae_vs_base_pct != null ? `${r.mejora_mae_vs_base_pct} %` : "—"}</dd></div>
              <div><dt><Term id="R2" /></dt><dd>{r.r2 ?? "—"}</dd></div>
              <div><dt>Aciertos del rango <Term id="p10-p90">p10–p90</Term> (esperado 80 %)</dt><dd>{r.cobertura_p10_p90 != null ? `${r.cobertura_p10_p90} %` : "—"}</dd></div>
              <div><dt>Entrenado el</dt><dd>{r.entrenado}</dd></div>
            </dl>
            {veredicto(r) && <p className="datos-veredicto" role="note">{veredicto(r)}</p>}
            <p className="panel-sub">
              El R² es alto porque los cultivos rinden muy distinto entre sí (una papa y un café no se parecen); por eso la comparación honesta es contra la línea base.
              Las predicciones guardadas son <Term id="fuera-de-muestra">fuera de muestra</Term>.
            </p>
          </>
        )}
        {d?.alerta && (
          <>
            <h4 className="datos-sub">Alertas climáticas</h4>
            <p>Puntaje F1 ponderado: <strong>{d.alerta.f1_ponderado ?? "—"}</strong> con {d.alerta.n_test != null ? nf.format(d.alerta.n_test) : "—"} observaciones de prueba (entrenado el {d.alerta.entrenado}).</p>
            <p className="panel-sub">El nivel de riesgo se define con reglas sobre la lluvia; el modelo predice ese índice del mes siguiente y se compara con «el mes siguiente repite el actual».</p>
          </>
        )}
        {d?.precios && (
          <>
            <h4 className="datos-sub">Pronóstico de precios</h4>
            <p>
              En pruebas con datos pasados, el error típico fue de <strong>{d.precios.error_modelo_pct ?? "—"} %</strong> con el modelo y de{" "}
              <strong>{d.precios.error_precio_hoy_pct ?? "—"} %</strong> suponiendo que el precio de mañana es el de hoy
              (hasta {d.precios.horizonte_max_dias_habiles ?? "—"} días hábiles).
            </p>
          </>
        )}

        <InfoPanel titulo="Límites conocidos">
          <ul>
            <li>Los datos de producción (EVA, datos.gov.co) cubren 2019–2025: pocos años para aprender tendencias.</li>
            <li>La aptitud de suelo (UPRA/SIPRA) no se usa: el servicio dejó de publicar las capas.</li>
            <li>El <Term id="SPI" /> se calcula con pocos años de clima, no con los 30 del índice clásico.</li>
            <li>Los ajustes por <Term id="ENSO" /> y lluvia del simulador son reglas orientativas, no salidas del modelo.</li>
            <li>Los precios cubren 36 productos frescos <Term id="mayorista">mayoristas</Term>; no incluyen granos, carnes, lácteos ni café.</li>
            <li>Es una herramienta de apoyo: no reemplaza la asistencia técnica agropecuaria.</li>
          </ul>
        </InfoPanel>
        <DataStamp fuente="model_version (métricas guardadas al entrenar)" fecha={r?.entrenado || null} />
      </Cargando>
    </Bloque>
  );
}

export default function PageDatos() {
  const estado = useApi("/api/estado");
  const catalogo = useApi("/api/catalogo");
  const calidad = useApi("/api/calidad");
  const modelo = useApi("/api/modelo/metricas");

  return (
    <section className="section">
      <div className="container">
        <div className="section-head">
          <span className="eyebrow">Transparencia</span>
          <h2>Datos y transparencia</h2>
          <p>De dónde sale cada cifra, qué tan frescos y completos están los datos y qué tan bien predice el modelo. Aquí vive el detalle; el resto de la app muestra solo el resumen.</p>
        </div>

        {estado.data?.datos_de_ejemplo && (
          <div className="datos-aviso" role="alert">
            <strong>Datos de ejemplo.</strong> Esta base fue sembrada con cifras inventadas para desarrollo (<code>scripts/seed_dev.py</code>): no las uses como información agrícola.
          </div>
        )}

        <div className="datos-grid">
          <EstadoSistema api={estado} />
          <FichaModelo api={modelo} />
          <Calidad api={calidad} />
          <Catalogo api={catalogo} />
        </div>
      </div>
    </section>
  );
}
