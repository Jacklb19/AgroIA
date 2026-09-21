"use client";
import { useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import Nav from "./components/Nav";
import Footer from "./components/Footer";
import PageInicio from "./components/PageInicio";
import PagePrecios from "./components/PagePrecios";
import PagePrediccion from "./components/PagePrediccion";
import OnboardingModal from "./components/OnboardingModal";
import { useHashRoute } from "@/lib/useHashRoute";

/* Las páginas pesadas o de consulta ocasional se cargan al visitarlas (no en el primer bundle). */
const Cargando = () => <div className="section"><div className="container"><div className="skel" style={{ height: 220 }} aria-label="Cargando" /></div></div>;
const PageDashboards  = dynamic(() => import("./components/PageDashboards"),  { loading: Cargando });
const PageAsistente   = dynamic(() => import("./components/PageAsistente"),   { loading: Cargando });
const PageDatos       = dynamic(() => import("./components/PageDatos"),       { loading: Cargando });
const PageMetodologia = dynamic(() => import("./components/PageMetodologia"), { loading: Cargando });
const PageImpacto     = dynamic(() => import("./components/PageImpacto"),     { loading: Cargando });

const TITULOS = {
  inicio: "Inicio", dashboards: "Dashboards", prediccion: "Predicción", precios: "Precios",
  asistente: "Asistente IA", datos: "Datos y transparencia", metodologia: "Metodología", impacto: "Impacto",
};

export default function App() {
  const { pagina, params, navegar, setParams } = useHashRoute();
  const primera = useRef(true);

  /* Al cambiar de página: título de la pestaña, scroll arriba y foco en el contenido (lectores de pantalla). */
  useEffect(() => {
    document.title = `${TITULOS[pagina]} · AgroIA Colombia`;
    if (primera.current) { primera.current = false; return; }
    window.scrollTo({ top: 0 });
    document.getElementById("main")?.focus({ preventScroll: true });
  }, [pagina]);

  const onNav = (destino, nuevos) => navegar(destino, nuevos);
  const ruta = { params, setParams };

  return (
    <>
      <OnboardingModal onNav={onNav} />
      <Nav active={pagina} onNav={onNav} />
      <main id="main" className="main" tabIndex={-1}>
        {pagina === "inicio"      && <PageInicio      onNav={onNav} />}
        {pagina === "dashboards"  && <PageDashboards  />}
        {pagina === "prediccion"  && <PagePrediccion  ruta={ruta} />}
        {pagina === "precios"     && <PagePrecios     ruta={ruta} />}
        {pagina === "asistente"   && <PageAsistente   />}
        {pagina === "datos"       && <PageDatos       />}
        {pagina === "metodologia" && <PageMetodologia />}
        {pagina === "impacto"     && <PageImpacto     onNav={onNav} />}
      </main>
      <Footer onNav={onNav} />
    </>
  );
}
