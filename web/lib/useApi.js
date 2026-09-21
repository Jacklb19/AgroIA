"use client";
import { useCallback, useEffect, useState } from "react";

/* Carga JSON desde una ruta /api con estados explícitos, para que ninguna pantalla invente datos:
     "loading" cargando · "ok" datos · "vacio" la ruta funcionó pero no hay datos (404) · "error" no disponible.
   `data` conserva el último resultado válido mientras se recarga. */
export function useApi(url, { enabled = true } = {}) {
  const [estado, setEstado] = useState({ status: "loading", data: null });
  const [intento, setIntento] = useState(0);
  const recargar = useCallback(() => setIntento((n) => n + 1), []);

  useEffect(() => {
    if (!enabled || !url) return undefined;
    const ctl = new AbortController();
    setEstado((prev) => ({ status: "loading", data: prev.data }));
    fetch(url, { signal: ctl.signal })
      .then(async (r) => {
        const cuerpo = await r.json().catch(() => null);
        if (r.status === 404) return setEstado({ status: "vacio", data: cuerpo });
        if (!r.ok) return setEstado({ status: "error", data: null });
        setEstado({ status: "ok", data: cuerpo });
      })
      .catch((e) => { if (e?.name !== "AbortError") setEstado({ status: "error", data: null }); });
    return () => ctl.abort();
  }, [url, enabled, intento]);

  return { ...estado, recargar };
}
