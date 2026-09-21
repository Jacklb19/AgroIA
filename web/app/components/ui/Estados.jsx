"use client";

/* Estados de interfaz compartidos: cargando, vacío y error. Ninguna pantalla debe mostrar
   datos de reemplazo: si no hay dato, se dice con claridad. */

export function Skeleton({ lineas = 3, alto = 14 }) {
  return (
    <div className="skel-wrap" role="status" aria-label="Cargando">
      {Array.from({ length: lineas }, (_, i) => (
        <div key={i} className="skel" style={{ height: alto, width: `${100 - i * 12}%` }} />
      ))}
    </div>
  );
}

export function EmptyState({ titulo = "Sin datos", texto, children }) {
  return (
    <div className="state-box empty" role="status">
      <strong>{titulo}</strong>
      {texto && <p>{texto}</p>}
      {children}
    </div>
  );
}

export function ErrorState({ texto = "Estos datos no están disponibles en este momento.", onReintentar }) {
  return (
    <div className="state-box error" role="alert">
      <strong>No se pudo cargar</strong>
      <p>{texto}</p>
      {onReintentar && (
        <button type="button" className="precios-limpiar" onClick={onReintentar}>Reintentar</button>
      )}
    </div>
  );
}

/* Muestra el estado adecuado según useApi, o los hijos cuando hay datos. */
export function Estado({ api, vacio, children }) {
  if (api.status === "loading" && !api.data) return <Skeleton />;
  if (api.status === "error") return <ErrorState onReintentar={api.recargar} />;
  if (api.status === "vacio") return vacio ?? <EmptyState texto="No hay datos para esta consulta." />;
  return children(api.data);
}
