"use client";
import { useState } from "react";
import { Icon } from "./icons";

const LINKS = [
  { id: "inicio",      label: "Inicio" },
  { id: "dashboards",  label: "Dashboards" },
  { id: "prediccion",  label: "Predicción" },
  { id: "asistente",   label: "Asistente IA" },
  { id: "metodologia", label: "Metodología" },
  { id: "impacto",     label: "Impacto" },
];

export default function Nav({ active, onNav }) {
  const [open, setOpen] = useState(false);

  const navigate = (id) => {
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

        <nav className="nav-links">
          {LINKS.map((l) => (
            <button
              key={l.id}
              className={`nav-link ${active === l.id ? "active" : ""}`}
              onClick={() => onNav(l.id)}
            >
              {l.label}
            </button>
          ))}
        </nav>

        <button className="nav-cta" onClick={() => onNav("prediccion")}>
          Consultar Predicción <Icon.arrow className="arrow" />
        </button>

        <button
          className={`nav-hamburger ${open ? "open" : ""}`}
          onClick={() => setOpen(!open)}
          aria-label="Menú"
        >
          <span />
          <span />
          <span />
        </button>
      </div>

      {open && (
        <div className="nav-mobile">
          {LINKS.map((l) => (
            <button
              key={l.id}
              className={`nav-mobile-link ${active === l.id ? "active" : ""}`}
              onClick={() => navigate(l.id)}
            >
              {l.label}
            </button>
          ))}
          <button className="nav-mobile-cta" onClick={() => navigate("prediccion")}>
            Consultar Predicción
          </button>
        </div>
      )}
    </header>
  );
}
