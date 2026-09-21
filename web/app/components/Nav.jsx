"use client";
import { useState } from "react";
import { Icon } from "./icons";

const LINKS = [
  { id: "inicio",      label: "Inicio" },
  { id: "dashboards",  label: "Dashboards" },
  { id: "prediccion",  label: "Predicción" },
  { id: "precios",     label: "Precios" },
  { id: "asistente",   label: "Asistente IA" },
  { id: "datos",       label: "Datos" },
  { id: "metodologia", label: "Metodología" },
  { id: "impacto",     label: "Impacto" },
];

export default function Nav({ active, onNav }) {
  const [open, setOpen] = useState(false);

  /* Son enlaces reales (#pagina): se pueden abrir en otra pestaña o copiar. El clic normal se maneja aquí. */
  const ir = (id) => (e) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;   // dejar que el navegador abra en pestaña nueva
    e.preventDefault();
    onNav(id);
    setOpen(false);
  };

  return (
    <header className="nav">
      <div className="container nav-inner">
        <div className="brand">
          <div className="brand-mark">A</div>
          <div className="brand-text">
            <strong>AgroIA Colombia</strong>
            <span>Inteligencia Agro-Climática</span>
          </div>
        </div>

        <nav className="nav-links" aria-label="Secciones">
          {LINKS.map((l) => (
            <a
              key={l.id}
              href={`#${l.id}`}
              className={`nav-link ${active === l.id ? "active" : ""}`}
              aria-current={active === l.id ? "page" : undefined}
              onClick={ir(l.id)}
            >
              {l.label}
            </a>
          ))}
        </nav>

        <a href="#prediccion" className="nav-cta" onClick={ir("prediccion")}>
          Consultar Predicción <Icon.arrow className="arrow" />
        </a>

        <button
          className={`nav-hamburger ${open ? "open" : ""}`}
          onClick={() => setOpen(!open)}
          aria-label="Menú"
          aria-expanded={open}
        >
          <span />
          <span />
          <span />
        </button>
      </div>

      {open && (
        <nav className="nav-mobile" aria-label="Secciones (móvil)">
          {LINKS.map((l) => (
            <a
              key={l.id}
              href={`#${l.id}`}
              className={`nav-mobile-link ${active === l.id ? "active" : ""}`}
              aria-current={active === l.id ? "page" : undefined}
              onClick={ir(l.id)}
            >
              {l.label}
            </a>
          ))}
          <a href="#prediccion" className="nav-mobile-cta" onClick={ir("prediccion")}>
            Consultar Predicción
          </a>
        </nav>
      )}
    </header>
  );
}
