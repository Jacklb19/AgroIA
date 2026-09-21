"use client";
import { useCallback, useMemo, useSyncExternalStore } from "react";

/* Navegación por hash: #precios?dep=Nariño&producto=12
   · El botón "atrás" funciona y cada vista es un enlace que se puede compartir.
   · Los cambios de filtros usan replaceState (no llenan el historial); cambiar de página sí agrega una entrada.
   · Solo viven en la URL los parámetros de la página activa; al cambiar de página se limpian. */

export const PAGINAS = ["inicio", "dashboards", "prediccion", "precios", "asistente", "datos", "metodologia", "impacto"];

const oyentes = new Set();
const notificar = () => oyentes.forEach((f) => f());

function suscribir(cb) {
  oyentes.add(cb);
  window.addEventListener("hashchange", cb);
  return () => { oyentes.delete(cb); window.removeEventListener("hashchange", cb); };
}

const leer = () => window.location.hash.slice(1);    // se deja codificado: URLSearchParams decodifica cada valor

export function parsearHash(hash) {
  const [pagina = "", consulta = ""] = String(hash).split("?");
  return {
    pagina: PAGINAS.includes(pagina) ? pagina : "inicio",
    params: new URLSearchParams(consulta),
  };
}

export function construirHash(pagina, params) {
  const p = params instanceof URLSearchParams ? params : new URLSearchParams(params || {});
  for (const [k, v] of [...p.entries()]) if (v === "" || v == null) p.delete(k);
  const q = p.toString();
  return q ? `${pagina}?${q}` : pagina;
}

function aplicar(hash, reemplazar) {
  if (reemplazar) {
    window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}#${hash}`);
    notificar();
  } else {
    window.location.hash = hash;    // dispara hashchange
  }
}

export function useHashRoute() {
  const crudo = useSyncExternalStore(suscribir, leer, () => "");   // en el servidor siempre "inicio"
  const { pagina, params } = useMemo(() => parsearHash(crudo), [crudo]);

  /* Ir a otra página (opcionalmente con parámetros). */
  const navegar = useCallback((destino, nuevos) => aplicar(construirHash(destino, nuevos), false), []);

  /* Cambiar parámetros de la página actual: null / "" los elimina. */
  const setParams = useCallback((cambio, { reemplazar = true } = {}) => {
    const actual = parsearHash(leer());
    const p = new URLSearchParams(actual.params);
    for (const [k, v] of Object.entries(cambio)) {
      if (v == null || v === "") p.delete(k);
      else p.set(k, String(v));
    }
    const nuevo = construirHash(actual.pagina, p);
    if (nuevo !== construirHash(actual.pagina, actual.params)) aplicar(nuevo, reemplazar);
  }, []);

  return { pagina, params, navegar, setParams };
}

/* Enlace absoluto a la vista actual (para "Copiar enlace"). */
export const enlaceActual = () => window.location.href;
