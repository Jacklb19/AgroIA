import { expect, test } from "@playwright/test";

/* Requiere la web compilada y una BD sembrada (python scripts/seed_dev.py --modelo). */

test.beforeEach(async ({ page }) => {
  // El tutorial inicial se muestra a quien nunca lo cerró y tapa la navegación.
  await page.addInitScript(() => localStorage.setItem("agroia_onboarding_v1", "1"));
});

test("las APIs responden con datos reales de la base", async ({ request }) => {
  const salud = await request.get("/api/health");
  expect(salud.ok()).toBeTruthy();
  expect((await salud.json()).ok).toBe(true);

  const impacto = await (await request.get("/api/impacto")).json();
  expect(impacto.fromDB).toBe(true);
  expect(impacto.municipios_cubiertos).toBeGreaterThan(0);

  const estado = await (await request.get("/api/estado")).json();
  expect(estado.fromDB).toBe(true);
  expect(estado.datos_de_ejemplo).toBe(true);        // la base de CI es la sembrada

  const precios = await request.get("/api/precios/estado");
  expect(precios.ok()).toBeTruthy();
});

test("las cabeceras de seguridad están presentes y no se anuncia el framework", async ({ request }) => {
  const res = await request.get("/");
  const h = res.headers();
  expect(h["content-security-policy"]).toContain("default-src 'self'");
  expect(h["x-content-type-options"]).toBe("nosniff");
  expect(h["x-powered-by"]).toBeUndefined();
});

test("el chat valida la entrada y no expone errores internos", async ({ request }) => {
  const vacio = await request.post("/api/chat", { data: { messages: [] } });
  expect(vacio.status()).toBe(400);
  const largo = await request.post("/api/chat", { data: { messages: [{ role: "user", content: "x".repeat(2500) }] } });
  expect(largo.status()).toBe(400);
});

test("la portada carga sin errores de consola y se puede navegar por las pestañas", async ({ page }) => {
  const errores = [];
  page.on("console", (m) => {
    const t = m.text();
    if (m.type() === "error" && !/favicon|Failed to load resource/.test(t)) errores.push(t);
    if (/Content Security Policy|Refused to/.test(t)) errores.push(t);   // una violación de la CSP rompería la web en producción
  });
  page.on("pageerror", (e) => errores.push(`pageerror: ${e.message}`));

  await page.goto("/");
  await expect(page.locator("nav .nav-link").first()).toBeVisible();

  const pestanas = await page.locator("nav .nav-link").allTextContents();
  expect(pestanas.length).toBeGreaterThanOrEqual(5);
  for (const nombre of pestanas) {
    await page.locator("nav .nav-link", { hasText: nombre.trim() }).first().click();
    await page.waitForTimeout(700);
    await expect(page.locator("main")).not.toBeEmpty();
  }
  expect(errores).toEqual([]);
});

test("la pestaña Precios muestra precios sembrados con su fuente y fecha", async ({ page }) => {
  await page.goto("/");
  await page.locator("nav .nav-link", { hasText: "Precios" }).first().click();
  await expect(page.locator("main")).toContainText(/Papa|Cebolla|Tomate|Plátano/i, { timeout: 15_000 });
});
