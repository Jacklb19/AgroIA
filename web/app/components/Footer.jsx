"use client";

const REPO = "https://github.com/Jacklb19/AgroIA";
const externo = { target: "_blank", rel: "noopener noreferrer" };

/* Enlaces reales (con href): se pueden usar con teclado y abrir en otra pestaña. Sin versiones ni fechas inventadas. */
export default function Footer({ onNav }) {
  const ir = (destino) => (e) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
    e.preventDefault();
    onNav(destino);
  };
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
          <nav className="footer-col" aria-label="Plataforma">
            <p className="footer-h">Plataforma</p>
            <a href="#inicio" onClick={ir("inicio")}>Inicio</a>
            <a href="#precios" onClick={ir("precios")}>Precios</a>
            <a href="#prediccion" onClick={ir("prediccion")}>Predicción</a>
            <a href="#dashboards" onClick={ir("dashboards")}>Dashboards</a>
          </nav>
          <nav className="footer-col" aria-label="Transparencia">
            <p className="footer-h">Transparencia</p>
            <a href="#datos" onClick={ir("datos")}>Datos y transparencia</a>
            <a href="#metodologia" onClick={ir("metodologia")}>Metodología</a>
            <a href="#impacto" onClick={ir("impacto")}>Impacto</a>
            <a href={REPO} {...externo}>Repositorio</a>
          </nav>
          <div className="footer-col">
            <p className="footer-h">Fuentes</p>
            <a href="https://www.dane.gov.co" {...externo}>DANE (SIPSA)</a>
            <a href="https://www.datos.gov.co" {...externo}>datos.gov.co (EVA)</a>
            <a href="https://www.ideam.gov.co" {...externo}>IDEAM</a>
            <a href="https://www.cpc.ncep.noaa.gov" {...externo}>NOAA (ENSO)</a>
          </div>
        </div>
        <div className="footer-bottom">
          <span>© {new Date().getFullYear()} AgroIA Colombia · Datos abiertos</span>
          <span>Herramienta de apoyo: no reemplaza la asistencia técnica agropecuaria</span>
        </div>
      </div>
    </footer>
  );
}
