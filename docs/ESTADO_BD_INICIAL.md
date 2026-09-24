# Estado inicial de la base de datos real (2026-09-23/24)

Primera carga end-to-end de AgroIA contra una base de datos real (no local, no sintética).
Este documento es una fotografía del momento en que se hizo la carga; para el estado actual
usa `/api/estado` y `/api/calidad`, que leen siempre de la BD.

## Infraestructura

- **Proveedor**: Railway Postgres (proyecto `agroia-colombia`, servicio `Postgres`, plan free),
  no Supabase. El plan original era Supabase, pero la cuenta disponible tenía el límite de
  proyectos free agotado (ver `ENV_BACKUP.md` para el detalle completo de la migración).
- Conexión externa vía proxy TCP público de Railway (`autorack.proxy.rlwy.net:16718`).
- Esquema aplicado con `python -m load.migrate` (5 migraciones versionadas + 2 repetibles),
  no con SQL suelto — `schema_migrations` queda coherente con lo que usa `/api/estado`.
- RLS activo en las 27 tablas; rol `agroia_web` de solo lectura (+ lectura/escritura en
  `chat_rate`/`chat_session`/`chat_message`), verificado con pruebas de escritura reales.

## Datos cargados (reales, trazables — nada inventado)

| Fuente | Tabla | Filas | Rango |
|---|---|---|---|
| EVA MinAgricultura (Socrata `uejq-wxrr`) | `fact_produccion_agricola` | 109,876 | 2007–2026, 1,122 municipios, 190 cultivos |
| IDEAM (precipitación, Socrata) | `fact_clima_mensual` | 17,511 | 2023–2026 (ver limitación abajo) |
| NOAA (ONI/ENSO) | `fact_alerta_enso` | 1,170 | — |
| DANE SIPSA-I (insumos) | `fact_precios_insumos` | 5,906 | — |
| DANE SIPSA (mensual histórico) | `fact_precios_mayoristas` | 304 | — |
| CNA 2014 | `fact_censo_agropecuario` | 1,121 | — |
| DANE SIPSA (SOAP diario, backfill) | `fact_precio_diario` | 696,084 | 2020-02-01 a 2026-09-23, 36 productos, 24 mercados |
| Pronóstico de precios (modelo) | `pred_precio` | 6,290 | 1–10 días hábiles |
| Modelo rendimiento (XGBoost) | `pred_rendimiento` | 64,577 | fuera de muestra, año de prueba 2025 |
| Modelo alerta climática | `pred_alerta_climatica` | 2,473 | — |
| UPRA/SIPRA (aptitud de suelo) | `fact_aptitud_suelo` | **0** | Servicio caído (sin cambio posible desde este repo) |

## Métricas del modelo (con datos reales, incluyendo clima 2023-2026)

- **Rendimiento** (`xgboost_rendimiento`): MAE 2.27 t/ha vs línea base 2.34 t/ha (mejora 2.65 %),
  R² 0.867, cobertura p10–p90 83 %. 44 variables, entrenado con CV por año (validación 2022-2024,
  prueba 2025 fuera de muestra).
- **Precios** (`xgboost_precio_diario`): MAE(log) 0.0798 vs. ingenuo 0.0814 (mejora 1.9 %),
  backtest de 4 cortes temporales.
- **Alerta climática** (`xgboost_alerta_anticipada`): exactitud 75.6 % (línea base persistencia 88.7 % —
  la etiqueta de riesgo es por reglas, no validada por expertos; ver nota en `model_version.metricas_json`).

## Limitaciones conocidas (aceptadas para esta carga, no ocultas)

1. **Clima IDEAM acotado a 2023-2026** (`CLIMA_YEAR_START` configurable, ver `config/settings.py`):
   el histórico completo (2018-2022) de temperatura/humedad tardaría 3-6h+ de descarga y no se
   corrió en esta ronda. Se puede completar más adelante quitando `CLIMA_YEAR_START` del entorno
   y re-corriendo `run_pipeline.py --mode core`.
2. **SIPRA/UPRA sigue caído**: `fact_aptitud_suelo` queda vacía, sin reemplazo conocido.
3. **Bug de esquema corregido en esta carga**: `fact_precios_insumos.unidad_medida` era
   `VARCHAR(20)`, insuficiente para el valor real de SIPSA-I ("Precio promedio de mercado (COP)",
   33 caracteres) — nunca se había probado contra Postgres real. Corregido en
   `migrations/005_ajustes_insumos.sql` (ampliado a VARCHAR(50)).
4. **Bug de rendimiento corregido en esta carga**: `load/db.py::upsert()` mandaba las filas una por
   una (`executemany` fila a fila de psycopg2/SQLAlchemy) en vez de un solo INSERT multi-fila —
   240 filas tardaban ~44s y 110,000 filas hubieran tardado horas. Corregido con
   `psycopg2.extras.execute_values` (110k filas ahora tardan ~2 minutos). Se agregó además un
   watchdog de timeout por lote (60s) con reintento en conexión nueva, por si la conexión al
   proxy de Railway se cae a medias.
5. **No hay despliegue automático (Railway cron) para refrescar estos datos todavía** — ver
   `CLAUDE.md` pendientes.

## Cómo reproducir esta carga

```powershell
python -m load.migrate                       # aplica el esquema
$env:CLIMA_YEAR_START = "2023"                # opcional: acota el histórico de clima
python run_pipeline.py --mode core --once
python run_pipeline.py --mode extended --once
python run_pipeline.py --mode models --once
python run_prices.py --mode init
python run_prices.py --mode backfill
python run_prices.py --mode forecast
python run_prices.py --mode informe
```
