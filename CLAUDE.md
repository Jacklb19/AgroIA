# AgroIA Colombia — LEER PRIMERO (contexto para Claude)

Este archivo lo carga Claude Code al abrir el proyecto. Resume **qué se hizo, cómo trabajar y qué falta**. Manténlo al día:
al terminar un trabajo relevante, actualiza las secciones 2, 6 y 7. No lo llenes de detalles que ya están en el código.

- **Repo**: `hackaton4\AgroH` (git, remoto `Jacklb19/AgroIA`). **Trabaja solo dentro de `AgroH`**, salvo que el usuario diga otra cosa.
- **Idioma**: responde en español. Sin emojis salvo que el usuario los use.
- **Nunca** toques la base real (Supabase) ni el Postgres del usuario (puerto 5433) sin permiso explícito. Ver sección 4.
- Estado: las 4 olas del plan de robustez están **hechas en local y SIN commit** (≈90 archivos). No hagas commit/push sin que el usuario lo pida.

## 1. Qué es el proyecto

Plataforma de datos abiertos del agro colombiano: **(a)** predicción de rendimiento por municipio × cultivo (XGBoost),
**(b)** alertas climáticas por reglas + modelo, **(c)** sección **Precios** (precios mayoristas diarios SIPSA-DANE, informe diario,
pronóstico 1–10 días hábiles, refresco horario), **(d)** asistente con Claude, **(e)** vistas para Power BI.
Stack: Python 3.13 (pandas 3, SQLAlchemy 2, xgboost), Postgres/Supabase, Next.js 14 (SPA con hash routing), Railway (cron), Vercel (web).

Principios que no se negocian:
1. **Nada inventado.** Sin dato → estado vacío / 404 / 503. Los datos sintéticos solo viven en `scripts/seed_dev.py` y están rotulados.
2. **Cada cifra visible** trazable a tabla + fecha (`DataStamp`, rutas con `web/lib/api.js`).
3. **NaN ≠ 0**: no `fillna(0)` en variables del modelo. Evaluación fuera de muestra y siempre contra la línea base.
4. **Errores internos no salen al cliente**: `errorBD()` (503 genérico + `request_id`) y logs JSON con `log()`.

## 2. Qué se ha hecho (plan de 4 olas, todas completas)

- **Sección Precios** (SIPSA): tablas `fact_precio_diario`, `pred_precio`, `informe_precio_diario`, `ingest_run`, vista `v_precio_actual`;
  `run_prices.py` (init/backfill/soap/hourly/informe/forecast); web `PagePrecios` + `/api/precios/*`. Guía: `docs/PRECIOS_PUESTA_EN_MARCHA.md`.
- **Ola 1 — credibilidad**: pipeline core corre de punta a punta; se eliminaron cifras/datos falsos de la portada y de las APIs;
  componentes `Estados`/`DataStamp`; chat protegido (límite por IP con hash + tope diario, validación, prompt sin "inventa cifras").
- **Ola 2 — modelo y datos válidos**: CV por año con año de prueba reservado; el modelo predice la desviación del promedio histórico;
  intervalos p10–p90 calibrados; predicciones solo fuera de muestra; índices ENSO/SPI reales; ANOVA correcto (Welch, Kruskal-Wallis, η², Holm);
  aptitud de suelo (SIPRA) **sin uso** (servicio caído); censo sin el 60/40 inventado.
- **Ola 3 — calidad y operación**: `migrations/` versionadas + `load/migrate.py`; config validada (`config/settings.py::db_config`);
  bitácora única `load/ingest_log.py` + alertas por webhook (`utils/alertas.py`, `ALERT_WEBHOOK_URL`); dependencias fijadas y separadas
  (`requirements*.txt`), `Dockerfile` + `Dockerfile.precios` multi-etapa, dependabot; CI estricto; RLS + rol `agroia_web` (solo lectura);
  cabeceras CSP; `docker-compose.yml`, `scripts/tasks.ps1`, `scripts/seed_dev.py`; `/api/estado`, `/api/calidad` desde la BD, logs con `request_id`.
- **Ola 4 — UX e información**: hash routing (`web/lib/useHashRoute.js`, filtros en la URL), página **Datos y transparencia** (`PageDatos.jsx`),
  glosario `<Term>`, `<InfoPanel>`, CSV (`web/lib/csv.js`, `?formato=csv`), widget "Precios de hoy", móvil (tarjetas), axe, `next/font`,
  favicon/OG, `docs/ARQUITECTURA.md`, `docs/RUNBOOK.md`, `docs/DICCIONARIO_DATOS.md` (generado).
- Resultados medidos: modelo con datos EVA reales y **sin clima** (2025 de prueba): MAE 2,26 vs línea base 2,34 t/ha (mejora ≈3 %), cobertura p10–p90 ≈83 %.
  Lighthouse local móvil 94/98/100/100. 167 tests Python, 33 E2E, cobertura ≈50 %.

## 3. Mapa del repo

```
config/  extract/  clean/  load/  models/  validate/  utils/     Python (ETL + modelos)
migrations/        001–004 versionadas + R__1_vistas, R__2_seguridad (repetibles)
scripts/           seed_dev.py · gen_data_dictionary.py · tasks.ps1
tests/             pytest (marca `db` = necesita Postgres desechable local)
web/               Next.js: app/components, app/api/*, lib/, e2e/ (Playwright + axe)
docs/              ARQUITECTURA, OPERACION, RUNBOOK, PRECIOS_PUESTA_EN_MARCHA, DICCIONARIO_DATOS (generado, no editar a mano)
run_pipeline.py    modos core|extended|models|all|precios|salud
run_prices.py      modos init|backfill|soap|hourly|informe|forecast
```

## 4. Cómo trabajar y probar en este equipo (Windows)

- **Herramientas**: la herramienta Bash NO tiene coreutils (sin cat/ls/tail/git); usa **PowerShell** y Read/Edit/Write/Grep/Glob.
  PowerShell bloquea comandos que contengan `rm -rf /var/...`: escribe Dockerfiles con Write. `python` del sistema es 3.13; usa `.\venv\Scripts\python.exe`.
- **Docker Desktop normalmente NO está corriendo**: `docker-compose.yml`, los Dockerfile y `tasks.ps1 setup/db-*` nunca se ejecutaron aquí.
- **Postgres de pruebas = PGlite** (WASM) en `<scratchpad>\pglite\server.mjs`, puerto **54329**, en memoria. Si no existe, se puede recrear con
  `@electric-sql/pglite` + `@electric-sql/pglite-socket`. Acepta **una sola sesión**: si Next se reinicia y todo falla a la vez, reinicia PGlite.
  Variables: `SUPABASE_DB_HOST=127.0.0.1 SUPABASE_DB_PORT=54329 SUPABASE_DB_USER=postgres SUPABASE_DB_PASSWORD=postgres`; para Next además `DB_*` y `DB_SSL=disable`.
- **Receta para ver la app local**: iniciar PGlite → `python scripts/seed_dev.py --reset --modelo` → (opcional) migrar y fijar contraseña del rol web
  (`python -m load.migrate --web-password` con `WEB_DB_PASSWORD`) → `cd web; npm run build; npm run start -- -p 3000`.
- **Pruebas**: `pytest` (con `TEST_DATABASE_URL=postgresql+psycopg2://postgres:postgres@127.0.0.1:54329/postgres` corren también las `db`; **borran el esquema `public`**,
  así que hay que resembrar después). `ruff check .` debe quedar limpio. Web: `npm run lint`, `npm run build`,
  `E2E_CHANNEL=chrome E2E_PORT=3100 npx playwright test` (contra `next start` ya levantado).
- `seed_dev.py` y las pruebas `db` se niegan a correr fuera de localhost. No lo evites.
- `next/og` falla con rutas con espacios (este equipo): la imagen OG es un PNG estático.

## 5. Datos y fuentes (lo que no sale del código)

- Producción: EVA `uejq-wxrr` (datos.gov.co), **2019–2025**. Clima IDEAM: descarga real tarda horas; **nunca se midió el modelo con clima real**.
- SIPSA: SOAP `appweb.dane.gov.co/sipsaWS` (historial ~300 MB) + Excel diario `anex-SIPSADiario-DDmmmAAAA.xlsx` (16 mercados; Barranquilla/Valledupar del Excel son promedios de ciudad y se excluyen).
- UPRA/SIPRA cayó: `fact_aptitud_suelo` queda vacía. Sin reemplazo conocido.

## 6. Pendientes y decisiones abiertas (actualiza esta lista)

1. **Nada está commiteado.** El usuario debe decidir: rama + PR (uno por ola o uno solo) y revisión en preview de Vercel.
2. **Next.js 14.2.35** (última 14.x) tiene avisos de `npm audit` (1 crítico, varios altos) que solo se corrigen en 15.5.24+/16. Decidir migración.
3. **Sin verificar nunca**: imágenes Docker, `docker-compose`, el workflow de GitHub Actions, aplicar las migraciones sobre el Supabase real
   (hacer copia antes; ver `docs/OPERACION.md`), cambiar Vercel a `DB_USER=agroia_web`.
4. Cobertura de pruebas ≈50 % (piso del CI 40 %); sin `ruff format` (reescribiría 64 archivos).
5. Modelo: mejora modesta sobre la línea base; medirlo con clima IDEAM real cuando se cargue.
6. Falta el "registro de cambios" en la página Datos (se puso "límites conocidos").
7. Definir `NEXT_PUBLIC_SITE_URL` en Vercel (imagen OG).

## 7. Cómo mantener este archivo

Al cerrar una tarea importante: mueve lo terminado de la sección 6 a la 2 (una línea), anota sorpresas del entorno en la 4 y los hechos de datos en la 5.
Las decisiones del usuario (p. ej. "usa Railway", "solo SIPSA en v1") van aquí, no solo en la conversación.
