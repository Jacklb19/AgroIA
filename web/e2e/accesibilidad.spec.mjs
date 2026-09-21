import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

/* Auditoría automática de accesibilidad (axe-core, reglas WCAG 2.0/2.1 A y AA) en cada pestaña.
   Falla con violaciones "serious" o "critical". Requiere BD sembrada. */

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("agroia_onboarding_v1", "1"));
});

const PAGINAS = ["inicio", "dashboards", "prediccion", "precios", "asistente", "datos", "metodologia", "impacto"];

for (const pagina of PAGINAS) {
  test(`axe: ${pagina} no tiene violaciones graves`, async ({ page }) => {
    await page.goto(`/#${pagina}`);
    await page.waitForTimeout(2500);        // deja cargar los datos y los gráficos
    const res = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    const graves = res.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    const resumen = graves.map((v) => `${v.id} (${v.impact}): ${v.help} → ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`);
    expect(resumen, resumen.join("\n")).toEqual([]);
  });
}

test("axe: el tutorial inicial (modal) es accesible", async ({ page }) => {
  await page.addInitScript(() => localStorage.removeItem("agroia_onboarding_v1"));
  await page.goto("/");
  await expect(page.getByRole("dialog")).toBeVisible();
  const res = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  const graves = res.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => `${v.id}: ${v.help}`);
  expect(graves).toEqual([]);
});
