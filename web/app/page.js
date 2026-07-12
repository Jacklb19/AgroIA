"use client";
import { useState } from "react";
import Nav from "./components/Nav";
import Footer from "./components/Footer";
import PageInicio from "./components/PageInicio";
import PageDashboards from "./components/PageDashboards";
import PagePrediccion from "./components/PagePrediccion";
import PageMetodologia from "./components/PageMetodologia";
import PageImpacto from "./components/PageImpacto";
import PageAsistente from "./components/PageAsistente";
import OnboardingModal from "./components/OnboardingModal";

export default function App() {
  const [active, setActive] = useState("inicio");

  const onNav = (page) => {
    setActive(page);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <>
      <OnboardingModal onNav={onNav} />
      <Nav active={active} onNav={onNav} />
      <main id="main" className="main" tabIndex={-1}>
        {active === "inicio"      && <PageInicio      onNav={onNav} />}
        {active === "dashboards"  && <PageDashboards  />}
        {active === "prediccion"  && <PagePrediccion  />}
        {active === "asistente"   && <PageAsistente   />}
        {active === "metodologia" && <PageMetodologia />}
        {active === "impacto"     && <PageImpacto     onNav={onNav} />}
      </main>
      <Footer onNav={onNav} />
    </>
  );
}
