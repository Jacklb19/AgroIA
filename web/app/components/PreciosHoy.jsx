"use client";
import { useApi } from "@/lib/useApi";
import { Estado, EmptyState } from "./ui/Estados";
import DataStamp from "./ui/DataStamp";
import Variacion from "./Variacion";
import { cop, fechaCorta } from "@/lib/formatoPrecios";

function Lista({ titulo, filas }) {
  return (
    <div className="ph-col">
      <h3>{titulo}</h3>
      {filas.length === 0 ? (
        <p className="ph-vacio">Sin movimientos destacados.</p>
      ) : (
        <ul>
          {filas.map((f) => (
            <li key={`${f.producto}:${f.mercado}`}>
              <span className="ph-prod"><strong>{f.producto}</strong><small>{f.mercado}</small></span>
              <span className="ph-num"><strong>{cop(f.precio)}</strong><Variacion v={f.var_pct} /></span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/* Widget de la portada: los mayores movimientos de precios del último informe diario. */
export default function PreciosHoy({ onNav }) {
  const api = useApi("/api/precios/informe");

  return (
    <section className="section" style={{ paddingTop: 48, paddingBottom: 8 }}>
      <div className="container">
        <div className="card">
          <div className="card-head">
            <div>
              <h2>Precios de hoy: lo que más se movió</h2>
              <div className="panel-sub">Precio mayorista por kilo · cambio frente al dato anterior</div>
            </div>
            <span className="src-badge">informe_precio_diario</span>
          </div>
          <div className="card-body">
            <Estado api={api} vacio={<EmptyState titulo="Aún no hay informe diario" texto="Cuando el sistema cargue precios del DANE aparecerán aquí." />}>
              {(d) => {
                const inf = d.informe || {};
                return (
                  <>
                    <div className="ph-grid">
                      <Lista titulo="Mayores subidas" filas={(inf.mayores_subidas_dia || []).slice(0, 4)} />
                      <Lista titulo="Mayores bajadas" filas={(inf.mayores_bajadas_dia || []).slice(0, 4)} />
                    </div>
                    <div className="ph-acciones">
                      <a href="#precios" className="precios-limpiar" onClick={(e) => { e.preventDefault(); onNav("precios"); }}>Ver todos los precios</a>
                      <a href="#precios?tab=informe" className="precios-limpiar" onClick={(e) => { e.preventDefault(); onNav("precios", { tab: "informe" }); }}>Leer el informe completo</a>
                    </div>
                    <DataStamp fuente="DANE — SIPSA" fecha={fechaCorta(d.fecha)} nota="DANE publica una vez por día hábil" />
                  </>
                );
              }}
            </Estado>
          </div>
        </div>
      </div>
    </section>
  );
}
