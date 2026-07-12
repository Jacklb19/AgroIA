"use client";

export default function Footer({ onNav }) {
  return (
    <footer className="footer">
      <div className="container">
        <div className="footer-grid">
          <div>
            <div className="footer-brand">
              <span className="mark">A</span>
              AgroIA Colombia
            </div>
            <p className="footer-tagline">
              Plataforma de inteligencia agroclimática con datos abiertos. Una solución madura, aplicable y auditable para el sector agropecuario colombiano.
            </p>
          </div>
          <div className="footer-col">
            <h5>Plataforma</h5>
            <a onClick={() => onNav("inicio")}>Inicio</a>
            <a onClick={() => onNav("dashboards")}>Dashboards</a>
            <a onClick={() => onNav("prediccion")}>Predicción</a>
          </div>
          <div className="footer-col">
            <h5>Equipo</h5>
            <a onClick={() => onNav("metodologia")}>Metodología</a>
            <a onClick={() => onNav("impacto")}>Impacto</a>
            <a>Repositorio</a>
          </div>
          <div className="footer-col">
            <h5>Fuentes</h5>
            <a>DANE</a>
            <a>IDEAM</a>
            <a>UPRA</a>
            <a>SIPSA</a>
          </div>
        </div>
        <div className="footer-bottom">
          <span>© 2026 AgroIA Colombia · Datos abiertos</span>
          <span>v1.4.2 · build 2026.04.28</span>
        </div>
      </div>
    </footer>
  );
}
