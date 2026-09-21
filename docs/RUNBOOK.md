# Runbook de incidentes

Primero mira **la pestaña Datos** de la web (o `GET /api/estado`): muestra la última corrida de cada proceso y los controles de calidad.
Cada 503 de la web trae un `request_id`; búscalo en los logs del servidor (líneas JSON).

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| Precios «Retrasado» / «Desactualizado» | El DANE aún no publicó, el cron no corrió o falló | `python run_prices.py --mode hourly`. Si falla, lee el error en `ingest_run` (`status='error'`). Los fines de semana y festivos es normal. |
| Alerta «Precios desactualizados» (webhook) | Último precio con > 3 días hábiles de atraso | Revisa el cron de Railway (`0 * * * *`) y sus logs; corre `--mode soap --dias 14` para ponerse al día. |
| Alerta «Falló la etapa pipeline_…» | Error en ETL o entrenamiento | El detalle está en `ingest_run.error`. Repite solo esa etapa: `python run_pipeline.py --mode core --once` (o `extended` / `models`). |
| Alerta «Calidad de datos: N en alerta» | Cobertura o duplicados fuera de umbral | Pestaña Datos → *Calidad*. Los umbrales están en `validate/quality_report.py`. |
| Web con «Los datos no están disponibles» (503) | Base caída, credenciales o SSL mal puestos, migración pendiente | `GET /api/health`; revisa `DB_*` y `DB_SSL` en Vercel; `python -m load.migrate --status`. |
| El chat responde 429 | Límite por IP o tope diario alcanzado | Es lo esperado; ajusta `CHAT_LIMIT_IP_DIA` / `CHAT_LIMIT_GLOBAL_DIA` si hace falta. |
| El chat responde 503 | Falta `ANTHROPIC_API_KEY`, o la tabla `chat_rate` no existe | Define la clave; corre `python -m load.migrate`. |
| `python -m load.migrate` dice «ya estaba aplicada y su contenido cambió» | Se editó una migración aplicada | Revierte el cambio y crea una migración nueva (`NNN_….sql`). |
| Migración falla con «permission denied» al crear el rol | El usuario no puede crear roles | Créalo con un administrador (`CREATE ROLE agroia_web LOGIN`) y corre `python -m load.migrate --force-repeatable`. |
| La web no lee tras cambiar a `agroia_web` | Contraseña sin fijar o usuario del pooler distinto | `python -m load.migrate --web-password`; en Supabase el usuario es `agroia_web.<ref-proyecto>`. |
| Predicciones vacías | Modelo sin entrenar o `pred_rendimiento` vacía | `python run_pipeline.py --mode models --once`. Necesita producción cargada. |
| CI falla en `gen_data_dictionary --check` | Cambió el esquema o una descripción | `python scripts/gen_data_dictionary.py` y sube `docs/DICCIONARIO_DATOS.md`. |

## Reinicio limpio de una base local

```powershell
.\scripts\tasks.ps1 db-reset   # borra el volumen de Docker y levanta Postgres
.\scripts\tasks.ps1 seed       # migra y siembra datos de EJEMPLO
```

**Nunca** ejecutes `seed_dev.py` ni las pruebas con marca `db` contra la base real: recrean el esquema. Ambos se niegan a correr fuera de
`localhost` / `127.0.0.1`.
