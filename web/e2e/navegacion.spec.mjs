import { expect, test } from "@playwright/test";

/* Ola 4: enlaces compartibles, "atrás", exportar, glosario, datos y transparencia, móvil. Requiere BD sembrada. */

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("agroia_onboarding_v1", "1"));
});

const hash = (page) => new URL(page.url()).hash;

test("cambiar de pestaña actualiza la URL y el botón atrás funciona", async ({ page }) => {
  await page.goto("/");
  await page.locator("nav .nav-link", { hasText: "Precios" }).first().click();
  await expect(page.locator("main")).toContainText("Precios mayoristas");
  expect(hash(page)).toBe("#precios");

  await page.locator("nav .nav-link", { hasText: "Datos" }).first().click();
  await expect(page.getByRole("heading", { name: "Datos y transparencia" })).toBeVisible();
  expect(hash(page)).toBe("#datos");

  await page.goBack();
  expect(hash(page)).toBe("#precios");
  await expect(page.locator("main")).toContainText("Precios mayoristas");
  await expect(page).toHaveTitle(/Precios · AgroIA/);
});

test("un enlace con filtros de precios reproduce la misma vista", async ({ page, request }) => {
  const listas = await (await request.get("/api/precios/filtros")).json();
  const dep = listas.departamentos[0].nombre;

  await page.goto("/");
  await page.locator("nav .nav-link", { hasText: "Precios" }).first().click();
  await page.locator("#pf-dep").selectOption(dep);
  await expect.poll(() => hash(page)).toContain(`dep=${encodeURIComponent(dep)}`);
  const enlace = page.url();

  const otra = await page.context().newPage();
  await otra.addInitScript(() => localStorage.setItem("agroia_onboarding_v1", "1"));
  await otra.goto(enlace);
  await expect(otra.locator("#pf-dep")).toHaveValue(dep);
  await expect(otra.locator("main")).toContainText("series");
});

test("abrir el historial de una serie queda en la URL y se restaura", async ({ page }) => {
  await page.goto("/#precios");
  const fila = page.locator(".precios-tabla tbody tr").first();
  await fila.click();
  await expect.poll(() => hash(page)).toMatch(/tab=historial&serie=\d+%3A\d+|tab=historial&serie=\d+:\d+/);
  const enlace = page.url();
  await page.goBack();
  expect(hash(page)).toBe("#precios");

  await page.goto("about:blank");
  await page.goto(enlace);
  await expect(page.getByRole("tab", { name: /Historial/ })).toHaveAttribute("aria-selected", "true");
});

test("una consulta de predicción compartida muestra el resultado ya calculado", async ({ page, request }) => {
  const municipios = await (await request.get("/api/municipios")).json();
  const cultivos = await (await request.get("/api/cultivos")).json();
  let combo = null;
  for (const m of municipios) {
    for (const c of cultivos) {
      const r = await request.post("/api/prediccion", { data: { muni: m, cultivo: c, year: String(new Date().getFullYear()), enso: "Neutral", lluvia: "Normal" } });
      if (r.ok()) { combo = { m, c }; break; }
    }
    if (combo) break;
  }
  test.skip(!combo, "La base sembrada no tiene predicciones (correr scripts/seed_dev.py --modelo)");

  await page.goto(`/#prediccion?m=${encodeURIComponent(combo.m)}&c=${encodeURIComponent(combo.c)}&run=1`);
  await expect(page.locator(".result-num")).toBeVisible({ timeout: 20_000 });
  await expect(page.locator("#pred-muni")).toHaveValue(combo.m);
  await expect(page.locator("#pred-cultivo")).toHaveValue(combo.c);
  await expect(page.locator(".data-stamp").first()).toContainText("pred_rendimiento");
});

test("descargar CSV de los precios (botón y API)", async ({ page, request }) => {
  await page.goto("/#precios");
  await expect(page.locator(".precios-tabla tbody tr").first()).toBeVisible();
  const [descarga] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Descargar CSV" }).click()]);
  expect(descarga.suggestedFilename()).toMatch(/^precios-mayoristas-.*\.csv$/);
  const fs = await import("fs/promises");
  const texto = await fs.readFile(await descarga.path(), "utf8");
  expect(texto.charCodeAt(0)).toBe(0xfeff);                                   // BOM para Excel
  expect(texto).toContain("Producto,Grupo,Mercado,Departamento");
  expect(texto.split("\r\n").length).toBeGreaterThan(5);

  const api = await request.get("/api/precios?formato=csv");
  expect(api.headers()["content-type"]).toContain("text/csv");
  expect(api.headers()["content-disposition"]).toContain("attachment");
});

test("la portada muestra los precios de hoy y enlaza al informe completo", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Precios de hoy/ })).toBeVisible();
  await expect(page.locator(".ph-col").first()).toContainText("Mayores subidas");
  await page.getByRole("link", { name: "Leer el informe completo" }).click();
  await expect.poll(() => new URL(page.url()).hash).toBe("#precios?tab=informe");
  await expect(page.getByRole("tab", { name: /Informe/ })).toHaveAttribute("aria-selected", "true");
});

test("el pie de página tiene enlaces reales y ninguna versión inventada", async ({ page }) => {
  await page.goto("/");
  const enlaces = await page.locator("footer a").evaluateAll((as) => as.map((a) => a.getAttribute("href")));
  expect(enlaces.length).toBeGreaterThan(6);
  expect(enlaces.every((h) => !!h)).toBe(true);
  await expect(page.locator("footer")).not.toContainText(/v\d+\.\d+\.\d+|build \d{4}/);
});

test("el glosario se abre con el teclado", async ({ page }) => {
  await page.goto("/#precios");
  const termino = page.locator(".term").first();
  await termino.focus();
  await expect(termino.locator("[role=tooltip]")).toBeVisible();
  await expect(termino.locator("[role=tooltip]")).toContainText("mayorista");
});

test("Datos y transparencia muestra estado, fuentes, calidad y ficha del modelo", async ({ page }) => {
  await page.goto("/#datos");
  await expect(page.getByRole("heading", { name: "Estado del sistema" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Ficha del modelo" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Calidad de los datos" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "De dónde salen los datos" })).toBeVisible();
  await expect(page.locator(".datos-aviso")).toContainText("Datos de ejemplo");      // la base de las pruebas es la sembrada
  await expect(page.locator("main")).toContainText("línea base");
  await expect(page.locator(".tabla-simple").first()).toBeVisible();
});

test.describe("móvil (375 px)", () => {
  test.use({ viewport: { width: 375, height: 800 } });

  for (const ruta of ["", "#dashboards", "#prediccion", "#precios", "#asistente", "#datos", "#metodologia", "#impacto"]) {
    test(`sin desborde horizontal en /${ruta}`, async ({ page }) => {
      await page.goto(`/${ruta}`);
      await page.waitForTimeout(1500);
      const ancho = await page.evaluate(() => ({ doc: document.documentElement.scrollWidth, ventana: window.innerWidth }));
      expect(ancho.doc).toBeLessThanOrEqual(ancho.ventana);
    });
  }

  test("los precios se muestran como tarjetas", async ({ page }) => {
    await page.goto("/#precios");
    await expect(page.locator(".precio-card").first()).toBeVisible();
    await expect(page.locator(".precios-tabla")).toBeHidden();
    await page.locator(".precio-card").first().click();
    await expect(page.getByRole("tab", { name: /Historial/ })).toHaveAttribute("aria-selected", "true");
  });

  test("el menú móvil navega con enlaces", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Menú" }).click();
    await page.locator(".nav-mobile-link", { hasText: "Datos" }).click();
    await expect(page.getByRole("heading", { name: "Datos y transparencia" })).toBeVisible();
  });
});
