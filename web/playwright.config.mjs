import { defineConfig } from "@playwright/test";

/* Humo E2E: se levanta la web ya compilada (npm run build) contra un Postgres sembrado con scripts/seed_dev.py.
   Local: E2E_CHANNEL=chrome usa el Chrome instalado (no hace falta descargar navegadores).
   CI:    npx playwright install --with-deps chromium */
const puerto = process.env.E2E_PORT || "3200";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${puerto}`,
    ...(process.env.E2E_CHANNEL ? { channel: process.env.E2E_CHANNEL } : {}),
    trace: "retain-on-failure",
  },
  webServer: {
    command: `npx next start -p ${puerto}`,
    url: `http://127.0.0.1:${puerto}/api/health`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
