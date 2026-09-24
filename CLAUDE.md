# AgroIA Colombia — LEER PRIMERO (contexto para Claude)

Este archivo lo carga Claude Code al abrir el proyecto. Resume **qué se hizo, cómo trabajar y qué falta**. Manténlo al día:
al terminar un trabajo relevante, actualiza las secciones 2, 6 y 7. No lo llenes de detalles que ya están en el código.

- **Repo**: `hackaton4\AgroH` (git, remoto `Jacklb19/AgroIA`). **Trabaja solo dentro de `AgroH`**, salvo que el usuario diga otra cosa.
- **Idioma**: responde en español. Sin emojis salvo que el usuario los use.
- La base de datos real vive en **Railway Postgres** (proyecto `agroia-colombia`), no Supabase — ver sección 5. Nunca la toques (migraciones, reseed, etc.) sin permiso explícito.
- Estado: las 4 olas del plan de robustez + Ola 5 (BD real poblada) están commiteadas en `mejoras-robustez` (pusheada a origin). No hagas commit/push sin que el usuario lo pida.

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
- Resultados medidos (seed local, sin clima): modelo con datos EVA reales y sin clima (2025 de prueba): MAE 2,26 vs línea base 2,34 t/ha (mejora ≈3 %), cobertura p10–p90 ≈83 %.
  Lighthouse local móvil 94/98/100/100. 167 tests Python, 33 E2E, cobertura ≈50 %.
- **Ola 5 — base de datos real (Railway Postgres, 2026-09-23/24)**: proyecto `agroia-colombia` en Railway (no Supabase, ver sección 5); esquema aplicado con `load/migrate.py`; RLS + `agroia_web` verificados con pruebas reales de escritura; datos reales cargados de punta a punta (producción EVA 109,876 filas, precios diarios SIPSA 696,084 filas, clima IDEAM 2023-2026, ENSO, insumos, censo, modelos entrenados — detalle completo en `docs/ESTADO_BD_INICIAL.md`). Se corrigieron dos bugs reales encontrados al probar contra Postgres real por primera vez: `fact_precios_insumos.unidad_medida` demasiado corta (`migrations/005_ajustes_insumos.sql`) y `load/db.py::upsert()` mandaba filas una por una en vez de un INSERT multi-fila (110k filas pasaron de "horas/colgado" a 2 minutos con `psycopg2.extras.execute_values`); también se corrigió `/api/recomendacion` para no confundir un fallo de BD con "sin alertas".

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

- Producción: EVA `uejq-wxrr` (datos.gov.co), **2007–2026** (109,876 filas reales cargadas). Clima IDEAM: descarga completa tarda horas; la carga real (2026-09-23) se acotó a **2023-2026** con `CLIMA_YEAR_START` (env var, default 2018 en código) — el histórico 2018-2022 queda pendiente de cargar cuando se quiera invertir el tiempo.
- SIPSA: SOAP `appweb.dane.gov.co/sipsaWS` (historial ~300 MB, 696,084 filas reales 2020-02 a hoy) + Excel diario `anex-SIPSADiario-DDmmmAAAA.xlsx` (16 mercados; Barranquilla/Valledupar del Excel son promedios de ciudad y se excluyen).
- UPRA/SIPRA cayó: `fact_aptitud_suelo` queda vacía. Sin reemplazo conocido.
- **Base de datos real**: Railway Postgres, proyecto `agroia-colombia` (no Supabase — la cuenta de Supabase disponible tenía el límite de proyectos free agotado; ver `ENV_BACKUP.md` para el detalle y `docs/ESTADO_BD_INICIAL.md` para el estado completo de la carga). Conexión externa vía proxy TCP público de Railway; credenciales en `.env`/`web/.env.local` (gitignored).

## 6. Pendientes y decisiones abiertas (actualiza esta lista)

1. **Merge a `main`**: `mejoras-robustez` sigue sin PR/merge. El usuario debe decidir cuándo.
2. **Next.js 14.2.35** (última 14.x) tiene avisos de `npm audit` (1 crítico, varios altos) que solo se corrigen en 15.5.24+/16. Decidir migración.
3. **Sin verificar nunca**: imágenes Docker, `docker-compose`, el workflow de GitHub Actions contra un entorno real (solo corre contra Postgres efímero del propio CI).
4. Cobertura de pruebas ≈50 % (piso del CI 40 %); sin `ruff format` (reescribiría 64 archivos).
5. **Clima IDEAM real solo 2023-2026** (no 2018-2022): completar corriendo `core` sin `CLIMA_YEAR_START` cuando se quiera invertir las horas que toma. Ver `docs/ESTADO_BD_INICIAL.md`.
6. Falta el "registro de cambios" en la página Datos (se puso "límites conocidos").
7. `web/app/api/anova` y `web/app/api/anova/imagen` son código muerto (leen `../data/quality_reports/` fuera de `web/`, nunca los llama el frontend — que ya usa `web/public/anova_data.json` estático). Detectado 2026-09-23, dejado sin tocar a pedido del usuario; candidato a limpieza futura.
8. **Railway solo tiene la base de datos**, no los crons de `run_pipeline.py`/`run_prices.py` — los datos no se refrescan solos todavía. Desplegarlos usando `Dockerfile`/`Dockerfile.precios` + `railway.json`/`railway.precios.json` ya existentes es el siguiente paso natural.
9. `web/.env.local` tenía una `GROQ_API_KEY` sin usar en el código — no se migró al nuevo `.env.local`, ver `ENV_BACKUP.md`.

## 7. Cómo mantener este archivo

Al cerrar una tarea importante: mueve lo terminado de la sección 6 a la 2 (una línea), anota sorpresas del entorno en la 4 y los hechos de datos en la 5.
Las decisiones del usuario (p. ej. "usa Railway", "solo SIPSA en v1") van aquí, no solo en la conversación.
