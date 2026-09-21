# Puesta en marcha de la sección Precios

Guía paso a paso para dejar funcionando la sección **Precios** (precios mayoristas diarios DANE-SIPSA, informe
diario y pronóstico) en tu Supabase, Railway y Vercel. Sigue los pasos **en orden**: cada uno depende del anterior.

> **Resumen de lo que vas a hacer**
> 1. Probar el código en tu computador (tests).
> 2. Crear las tablas nuevas en Supabase y cargar el historial (comandos locales).
> 3. Verificar los datos con SQL.
> 4. Probar la web en local.
> 5. Crear el servicio de Railway que actualiza cada hora.
> 6. Subir el código a GitHub para que Vercel publique la web.
> 7. Verificar en producción.

Tiempo estimado: **45–60 minutos** (la mayor parte es esperar descargas y el primer entrenamiento).

---

## 0. Antes de empezar

| Necesitas | Cómo comprobarlo |
|---|---|
| Python con el `venv` del proyecto | `.\venv\Scripts\python.exe --version` |
| Node 20+ | `node --version` |
| Credenciales de Supabase (las mismas de siempre) | Tu archivo `.env` (ver paso 1) |
| Acceso a Railway y Vercel | Ya los usas para `agroia-colombia` |
| ~1 GB libre en disco y buena conexión | El historial de DANE pesa ~300 MB (se borra al terminar) |

Todos los comandos se ejecutan en **PowerShell**, desde la carpeta `AgroH`:

```powershell
cd "C:\Users\Steven\Desktop\Universidad\semestre 6\analisis de datos\hackaton4\AgroH"
.\venv\Scripts\Activate.ps1
```

> Si PowerShell bloquea la activación: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` y vuelve a intentar.

---

## 1. Revisar el `.env` (credenciales de Supabase)

El script de Python lee `AgroH\.env`. Debe tener estas variables (son las mismas que ya usas para `run_pipeline.py`):

```ini
SUPABASE_DB_HOST=...        # ver nota sobre IPv6 abajo
SUPABASE_DB_PORT=5432
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres   # con el pooler es: postgres.<ref-del-proyecto>
SUPABASE_DB_PASSWORD=...
```

> **Nota IPv6 (importante para Railway):** el host directo `db.<ref>.supabase.co` de Supabase solo responde por
> IPv6 y Railway puede no alcanzarlo. Si en el paso 5 ves errores de conexión, usa el **Session pooler**
> (Supabase → *Project Settings → Database → Connection string → Session pooler*): host
> `aws-0-<region>.pooler.supabase.com`, puerto `5432`, usuario `postgres.<ref-del-proyecto>`.
> Para tu computador cualquiera de los dos sirve.

Instala dependencias (por si falta alguna) y `pytest`:

```powershell
pip install -r requirements.txt
pip install pytest
```

---

## 2. Correr los tests (no toca ninguna base de datos)

```powershell
pytest -q
```

Debe terminar con `40 passed`. Si algo falla, **detente aquí** y avísame con el mensaje.

---

## 3. Crear las tablas nuevas en Supabase

Este paso es **aditivo**: crea tablas nuevas y no borra ni modifica datos existentes. Lo único que toca en tablas
existentes es agregar 2 columnas vacías a `dim_central_abastos` (`id_departamento`, `nombre_departamento`).
Las vistas de Power BI **no** se tocan.

**Opcional pero recomendado — respaldo:** en Supabase → *Database → Backups* confirma que hay un respaldo reciente
(o descarga uno manual).

```powershell
python run_prices.py --mode init
```

Crea: `dim_producto_precio`, `fact_precio_diario`, `pred_precio`, `informe_precio_diario`, `ingest_run` y la vista
`v_precio_actual`. Es seguro repetirlo.

### 3.1 (Recomendado) Bloquear el acceso público a las tablas nuevas

Supabase expone por defecto las tablas del esquema `public` a su API pública si no tienen RLS. Tu app se conecta
directo a Postgres con el usuario `postgres` (que ignora RLS), así que puedes activarlo sin romper nada.
En Supabase → *SQL Editor* ejecuta:

```sql
ALTER TABLE dim_producto_precio    ENABLE ROW LEVEL SECURITY;
ALTER TABLE fact_precio_diario     ENABLE ROW LEVEL SECURITY;
ALTER TABLE pred_precio            ENABLE ROW LEVEL SECURITY;
ALTER TABLE informe_precio_diario  ENABLE ROW LEVEL SECURITY;
ALTER TABLE ingest_run             ENABLE ROW LEVEL SECURITY;
```

> Solo hazlo si `DB_USER` / `SUPABASE_DB_USER` es `postgres` (o el dueño de las tablas). Si usaras otro rol sin
> permiso de saltarse RLS, las consultas devolverían vacío.

---

## 4. Cargar el historial (una sola vez)

```powershell
python run_prices.py --mode backfill
```

Qué hace: descarga el historial diario completo de DANE por el servicio SOAP (~300 MB, ~1–2 min), lo limpia y lo
carga (~700.000 filas). Al terminar borra el archivo descargado.

Salida esperada al final:

```
Resultado: {'status': 'ok', 'ref': 'full', 'filas': 694866, ...}
```

(`filas` puede ser algo mayor con el tiempo, porque DANE agrega datos cada día hábil.)

Si se corta a la mitad, **vuelve a ejecutarlo**: es idempotente (no duplica filas).

### 4.1 Generar el informe y el pronóstico por primera vez

```powershell
python run_prices.py --mode informe      # segundos
python run_prices.py --mode forecast     # ~10–12 minutos, usa ~1,5 GB de RAM
```

El pronóstico entrena un modelo con backtest. Déjalo terminar; al final imprime algo como
`{'status': 'ok', 'predicciones': 6260, 'confianza': {...}}`.

> Este es el único paso pesado. Haz esta primera corrida **manual** para confirmar que tu equipo aguanta la memoria
> antes de dejarlo en Railway.

---

## 5. Verificar los datos en Supabase (SQL Editor)

```sql
-- 1) Debe haber ~695.000 filas, desde 2020-02 hasta el último día hábil
SELECT COUNT(*), MIN(fecha), MAX(fecha) FROM fact_precio_diario;

-- 2) Deben ser ~24 mercados en ~20 departamentos, sin mercados repetidos
SELECT COUNT(*), COUNT(DISTINCT nombre_central), COUNT(DISTINCT nombre_departamento)
FROM dim_central_abastos WHERE id_departamento IS NOT NULL;

-- 3) Ejemplo: papa criolla en Pasto
SELECT mercado, producto, fecha, precio_prom_kg, var_dia_pct, var_7d_pct
FROM v_precio_actual
WHERE departamento = 'Nariño' AND producto = 'Papa criolla';

-- 4) Informe y pronóstico generados
SELECT fecha, generado_at FROM informe_precio_diario ORDER BY fecha DESC LIMIT 3;
SELECT COUNT(*), MIN(fecha_objetivo), MAX(fecha_objetivo) FROM pred_precio;

-- 5) Bitácora: no debe haber errores
SELECT id, fuente, status, filas_nuevas, fecha_dato_max, error
FROM ingest_run ORDER BY id DESC LIMIT 10;
```

Qué esperar: (1) ≈694.000+ filas; (2) 24 mercados; (3) una fila de Pasto; (4) 1+ informe y ≈6.000 predicciones;
(5) todo en `ok`.

---

## 6. Probar la web en tu computador

Crea `AgroH\web\.env.local` (este archivo está ignorado por git) con las credenciales de Supabase de la web:

```ini
DB_HOST=...
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=...
ANTHROPIC_API_KEY=...
```

Luego:

```powershell
cd web
npm install
npm run dev
```

Abre <http://localhost:3000> → pestaña **Precios**. Debes ver:

- [ ] La franja "Al día" con la fecha del último dato y la hora de publicación de DANE.
- [ ] La tabla con cientos de filas; al elegir *Nariño* + *Papa criolla* aparece Pasto.
- [ ] Al tocar una fila, el historial con el gráfico y el pronóstico.
- [ ] La pestaña **Informe del día** con subidas, bajadas y brecha entre mercados.

Si la web dice "Los precios no están disponibles", revisa `web\.env.local` y que el paso 4 haya terminado.
Detén el servidor con `Ctrl+C` y vuelve a la carpeta raíz: `cd ..`.

---

## 7. Servicio de Railway (actualización cada hora)

Crea un **segundo servicio** en el mismo proyecto de Railway (el servicio semanal que ya tienes no se toca).

1. Railway → tu proyecto → **New → GitHub Repo** → elige el repo `AgroIA`.
2. En el servicio nuevo → **Settings → Config-as-code → Path**: escribe `railway.precios.json`.
   (Ese archivo define `startCommand: python run_prices.py --mode hourly`, cron `0 * * * *` y no reiniciar.)
3. **Variables**: agrega las mismas `SUPABASE_DB_*` del paso 1 (puedes copiarlas del servicio existente).
   Para Railway usa el host del **Session pooler** si el directo no conecta (ver nota IPv6).
4. **Settings → Resources**: asegura **≥ 2 GB de memoria** (el pronóstico usa ~1,5 GB).
5. Haz **Deploy**. El primer disparo ocurre en el siguiente minuto `:00` (el cron corre en hora UTC).

> ⚠️ Haz este paso **después** de subir el código a GitHub (paso 8): Railway construye desde el repo, y
> `railway.precios.json` y `run_prices.py` todavía no están allí.

**Cómo saber que funciona:** en los *Logs* del servicio verás cada hora líneas como
`SIPSA Excel 18sep2026 sin cambios` y `Resultado: {... 'soap': {'status': 'al_dia'} ...}`. Cuando DANE publique un
día nuevo, esa ejecución tardará más (descarga el SOAP y reentrena, unos 3–4 minutos con backtest reutilizado).

Comportamiento normal:

- Fines de semana y festivos: `sin cambios` (DANE no publica).
- Si el SOAP va atrasado respecto al Excel, reintenta la descarga incremental cada 2 horas.
- Una vez por semana reconcilia todo el historial y reentrena el backtest.

---

## 8. Subir el código a GitHub (publica la web en Vercel)

Vercel despliega solo cuando llegan cambios a `main`. Te recomiendo hacerlo por rama y revisar la vista previa:

```powershell
cd "C:\Users\Steven\Desktop\Universidad\semestre 6\analisis de datos\hackaton4\AgroH"
git checkout -b feature/precios
git add clean config extract load migrations models utils scripts tests web docs README.md run_prices.py run_pipeline.py railway.precios.json Dockerfile Dockerfile.precios requirements.txt requirements-precios.txt requirements-dev.txt
git status          # revisa que NO aparezcan .env, data/ ni logs/
git commit -m "Seccion Precios: precios mayoristas diarios SIPSA, informe y pronostico"
git push -u origin feature/precios
```

Luego abre un Pull Request en GitHub hacia `main`. Vercel crea una **vista previa** del PR; ábrela y repite la
lista del paso 6. Cuando esté bien, haz *Merge*.

> `web/app/components/PageAsistente.jsx` ya tenía un cambio tuyo sin commitear (botón de voz). `git add web` lo
> incluye; si no quieres subirlo todavía, excluye ese archivo: `git restore --staged web/app/components/PageAsistente.jsx`.

**Variables de entorno en Vercel:** no necesitas ninguna nueva. Confirma en *Project → Settings → Environment
Variables* que existen `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` y `ANTHROPIC_API_KEY`.
**No** definas `DB_SSL` en Vercel (es solo para desarrollo local).

---

## 9. Verificación final en producción

- [ ] <https://agroia-colombia.vercel.app/api/precios/estado> → `"estado": "al_dia"` y `fecha_dato_max` reciente.
- [ ] La pestaña **Precios** muestra datos y el historial de una fila carga.
- [ ] Railway → *Logs*: la ejecución de la hora en punto termina sin errores.
- [ ] Preguntas al asistente: *"¿a cómo está la papa criolla en Pasto?"* responde con el precio y la fecha, sin inventar.
- [ ] Al día siguiente de un día hábil, `datos_actualizados_at` (en `/api/precios/estado`) cambia solo.

---

## Problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `ImportError` / `ModuleNotFoundError` al correr `run_prices.py` | Falta activar el venv o instalar dependencias | `.\venv\Scripts\Activate.ps1` y `pip install -r requirements.txt` |
| Error de conexión / *timeout* en Railway | Host directo de Supabase es solo IPv6 | Usa el **Session pooler** (paso 1) |
| `SSL` / `does not support SSL` en local | Postgres local sin SSL | Solo para una BD local: `DB_SSL=disable` en `web\.env.local` |
| `SIPSA SOAP` falla con 415 o "respuesta inesperada" | El servicio exige **SOAP 1.2** | El código ya lo usa; si persiste, DANE cambió el servicio (avísame) |
| La web dice "Los precios no están disponibles" (503) | Variables `DB_*` mal puestas o paso 3/4 sin hacer | Revisa variables y ejecuta `--mode init` y `--mode backfill` |
| Estado "Retrasado/Desactualizado" un lunes o festivo | El sistema no conoce los festivos colombianos | Es normal; se corrige al día hábil siguiente |
| La tabla no muestra papa negra en Pasto | Pasto dejó de reportarla en nov-2020 | Es real: es un dato ausente en la fuente, no un error |
| Railway mata el proceso durante el pronóstico | Poca memoria | Sube la memoria del servicio a ≥ 2 GB |
| El pronóstico sale casi igual al precio de hoy | Es lo que el backtest justifica (mejora ~2 % global) | Es esperado; la web lo explica y muestra la confianza |

---

## Mantenimiento

- **Ver el estado:** `/api/precios/estado` y la tabla `ingest_run` (columna `error`).
- **Forzar una carga manual:** `python run_prices.py --mode soap --dias 14` (últimos 14 días) o `--mode hourly`.
- **Regenerar informe/pronóstico:** `--mode informe` / `--mode forecast`.
- **Aplicar cambios futuros al esquema de precios:** `python run_prices.py --mode init`.

## Deshacer todo (rollback)

Si quieres quitar la sección por completo, en el *SQL Editor* de Supabase:

```sql
DROP VIEW  IF EXISTS v_precio_actual CASCADE;
DROP TABLE IF EXISTS pred_precio, informe_precio_diario, fact_precio_diario, ingest_run, dim_producto_precio CASCADE;
ALTER TABLE dim_central_abastos DROP COLUMN IF EXISTS id_departamento, DROP COLUMN IF EXISTS nombre_departamento;
-- Opcional: mercados creados por esta sección (nombres nuevos, p. ej. 'Bogotá, Corabastos')
-- DELETE FROM dim_central_abastos WHERE id_central NOT IN (SELECT DISTINCT id_central FROM fact_precios_mayoristas);
-- Opcional: versiones del modelo de precios
DELETE FROM model_version WHERE nombre_modelo = 'xgboost_precio_diario';
```

Y en Railway elimina el servicio nuevo. Las demás tablas, vistas y Power BI no se ven afectadas.

---

## Pendientes conocidos (fuera de esta sección)

Cosas que encontré en el análisis del proyecto y que **no** cambié aquí:

1. `run_pipeline.py --mode core` falla hoy (`SOCRATA_TOKEN` no existe en `config/settings.py` y las columnas de
   producción no coinciden). El servicio semanal existente de Railway (`railway.json`) ejecuta ese pipeline.
2. Las rutas `/api/impacto`, `/api/dashboards` y `/api/mapa` se pre-renderizan en el *build* de Next 14, por lo que
   en producción pueden mostrar datos congelados o valores de respaldo.
3. `/api/chat` no tiene autenticación ni límite de uso y consume tu `ANTHROPIC_API_KEY`.
