# Operación de AgroIA

Guía corta para quien mantiene el sistema: migraciones, base de datos segura, alertas, imágenes y CI.

## 1. Migraciones de la base de datos

Todo cambio de esquema vive en `migrations/` y se aplica con **un** comando:

```bash
python -m load.migrate            # aplica lo pendiente (idempotente)
python -m load.migrate --status   # qué está aplicado y qué falta, sin cambiar nada
```

| Archivo | Contenido |
|---|---|
| `001_base.sql` | Dimensiones, hechos, tablas del modelo y memoria del chat |
| `002_precios.sql` | Precios diarios SIPSA, pronósticos, informe diario, bitácora `ingest_run` |
| `003_chat_rate.sql` | Contadores diarios del asistente |
| `004_observabilidad.sql` | `quality_check_run` y `extraction_report` |
| `R__1_vistas.sql` | Vistas para Power BI y la web (repetible) |
| `R__2_seguridad.sql` | RLS y rol de solo lectura (repetible) |

Reglas:
- **No se edita una migración ya aplicada** (el checksum lo detecta y falla). El cambio va en una nueva `NNN_nombre.sql`.
- Las migraciones deben ser idempotentes (`IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`…). Por eso una base creada antes
  con `schema.sql` (que ya tenía las tablas) simplemente las adopta sin cambios.
- Las `R__*.sql` se reaplican cuando cambia el archivo o cuando se aplica una migración versionada nueva.
- Todo lo pendiente se aplica en **una transacción** con candado: si algo falla no queda a medias, y dos procesos
  simultáneos (un despliegue y el cron) no se pisan.
- Las vistas usan `CREATE OR REPLACE` (sin `DROP … CASCADE`). Si cambias las columnas de una vista, crea una migración
  versionada que la elimine antes.
- El ETL (`--mode core` / `extended` / `all`) y `run_prices.py` aplican lo pendiente al arrancar; no hace falta correr `migrate` a mano en cada despliegue.

**Primera vez sobre tu base actual (Supabase):** haz primero una copia (Supabase → Database → Backups) y ejecuta
`python -m load.migrate`. Activa RLS en las tablas de AgroIA: el usuario `postgres` (y cualquier rol dueño) la omite,
así que el ETL, la web y Power BI conectados con ese usuario siguen funcionando; solo dejan de ver filas los roles
`anon` / `authenticated` de la API REST de Supabase, que AgroIA no usa.

## 2. Rol de solo lectura para la web

`R__2_seguridad.sql` crea el rol `agroia_web`: **lee todo, escribe solo en `chat_session`, `chat_message` y `chat_rate`**
y no puede crear ni borrar nada. Se crea sin contraseña. Para activarlo:

1. En `.env`: `WEB_DB_PASSWORD=<12+ caracteres aleatorios>` y `python -m load.migrate --web-password`.
2. En Vercel cambia `DB_USER=agroia_web` y `DB_PASSWORD=<esa contraseña>`; vuelve a desplegar.
3. Comprueba `/api/health` y el chat.

Si tu proveedor no deja crear roles con el usuario de las migraciones, la migración lo avisa y sigue (créalo con un
usuario administrador y vuelve a correr `python -m load.migrate --force-repeatable`).

Con **Supabase Pooler (Supavisor)** el nombre de usuario lleva el proyecto (`agroia_web.<ref>`); usa el que muestre el panel.

## 3. SSL y tiempos de espera de la web

| Variable | Efecto |
|---|---|
| `DB_SSL=disable` | Sin SSL (solo local) |
| `DB_SSL=require` (por defecto) | Cifra sin verificar el certificado |
| `DB_SSL=verify-full` + `DB_SSL_CA` | Cifra y verifica (pega el PEM de la CA; los saltos de línea pueden ir como `\n`) |
| `DB_STATEMENT_TIMEOUT_MS` | Tope de tiempo por consulta en el servidor (opcional; algunos poolers no lo aceptan) |

Cada consulta ya tiene además un tope de 20 s en el cliente. La web envía cabeceras de seguridad (CSP, `X-Frame-Options`,
`Referrer-Policy`…) definidas en `web/next.config.mjs`; si añades un recurso externo (otra fuente, otro iframe) hay que
declararlo ahí o el navegador lo bloqueará.

## 4. Bitácora y alertas

Todas las etapas quedan en la tabla `ingest_run`: `pipeline_core`, `pipeline_extended`, `pipeline_models` y las de precios
(`sipsa_excel`, `sipsa_soap`, `forecast_precio`). `/api/estado` muestra la última corrida de cada una.

Si defines `ALERT_WEBHOOK_URL` (Slack, Discord o Teams) recibirás un mensaje cuando:
- una etapa del pipeline falla o el job de precios se cae,
- el pronóstico o el informe fallan (aviso),
- algún control de calidad entra en **ALERTA**,
- el último precio cargado lleva más de 3 días hábiles de atraso, o una etapa del pipeline lleva más de 10 días sin terminar bien.

Los avisos de frescura no se repiten en 12 horas. `python run_pipeline.py --mode salud --once` solo revisa frescura.

Los logs de la web son una línea JSON con `request_id` (también en la cabecera `x-request-id` y en el cuerpo de los 503),
así que un reporte de un usuario se busca en el log por ese identificador.

## 5. Imágenes Docker y Railway

| Imagen | Uso | Dependencias |
|---|---|---|
| `Dockerfile` | ETL completo y entrenamiento (`railway.json`, lunes 07:00 UTC) | `requirements.txt` |
| `Dockerfile.precios` | Job horario de precios (`railway.precios.json`, `0 * * * *`) | `requirements-precios.txt` (sin geopandas, optuna, shap…) |

Las versiones están fijadas (`==`); Dependabot propone actualizaciones semanales y el CI las prueba.

## 6. CI (`.github/workflows/ci.yml`)

| Job | Qué verifica |
|---|---|
| `lint` | `ruff check` (sin `|| true`: un aviso falla el CI) |
| `python-tests` | Postgres 16: migraciones desde cero dos veces, diccionario de datos al día, pytest (incluye pruebas `db`), cobertura mínima |
| `precios-minimo` | El servicio de precios funciona solo con `requirements-precios.txt` |
| `web` | `next lint`, `next build`, `npm audit` (informativo), siembra de datos, humo E2E y navegación (Playwright) y accesibilidad (axe: sin violaciones graves) |
| `docker` | Se construyen las dos imágenes y la de precios arranca |

## 7. Pendientes conocidos

- **Next.js 14.2.35** (última 14.x) tiene avisos de seguridad que solo se corrigen en 15.5.24+ / 16 (cambio mayor).
  Mitigaciones actuales: la app no usa `next/image`, Server Actions ni rewrites, y se despliega en Linux. Planificar la migración.
- La cobertura de pruebas de `clean/`, `load/` y `utils/` es ≈ 50 % (umbral del CI: 40 %, debe subir con el tiempo; `load_facts.py` y los limpiadores de clima/insumos son lo menos cubierto).
- No hay comprobación de formato (`ruff format`): aplicarla reescribiría la mayoría de los archivos; se hará en un PR aparte.
