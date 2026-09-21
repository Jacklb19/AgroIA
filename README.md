# 🌾 AgroIA Colombia — Dashboard de Inteligencia Agro-Climática

> **Sistema de Inteligencia para la Resiliencia Agrícola Colombiana**  
> Plataforma integral que fusiona datos climáticos, precios de insumos y producción histórica para predecir rendimientos de cultivos y anticipar riesgos agroclimáticos en Colombia.

## 🌱 Título del Proyecto

**AgroIA Colombia: Dashboard de Inteligencia Agro-Climática para la Predicción de Rendimientos Agrícolas y Análisis de Riesgo Climático**

---

## ⚠️ Problema Abordado

Colombia es una de las naciones con mayor diversidad agroclimática del mundo, con más de **1.100 municipios** donde la agricultura es la principal actividad económica. Sin embargo, los agricultores y tomadores de decisiones enfrentan tres grandes retos críticos:

1. **Volatilidad climática extrema**: Los fenómenos ENSO (El Niño y La Niña) generan variaciones drásticas en precipitación y temperatura que pueden reducir hasta un **40% el rendimiento** de cultivos transitorios como maíz, papa y arroz.

2. **Falta de herramientas predictivas accesibles**: Los productores rurales toman decisiones de siembra basadas en experiencia empírica, sin acceso a modelos de predicción de rendimiento que integren datos reales de clima, suelos y precios de mercado.

3. **Información fragmentada y dispersa**: Los datos relevantes están distribuidos en al menos 8 sistemas distintos (IDEAM, DANE, UPRA, NOAA, NASA) sin una capa de integración que los conecte y haga accionables.

**AgroIA Colombia** resuelve este problema construyendo un pipeline de datos completo y una plataforma web de inteligencia agro-climática que integra todas estas fuentes en un solo lugar.

---

## 💡 Justificación (Valor Público)

| Dimensión | Impacto |
|-----------|---------|
| **Seguridad alimentaria** | Colombia destina ~42% de su territorio a actividades agropecuarias; mejorar la predicción de rendimientos tiene efecto directo en la oferta alimentaria nacional |
| **Inclusión tecnológica** | Democratiza el acceso a inteligencia de datos para pequeños y medianos productores que no tienen equipos de analítica |
| **Gestión del riesgo** | Permite a entidades como Finagro, ADR y gobernaciones anticipar crisis agrícolas con al menos un año de antelación |
| **Eficiencia del gasto público** | Permite focalizar subsidios, crédito y asistencia técnica en los municipios de mayor riesgo climático-productivo |
| **Open Data** | El 80% de los datos fuente son abiertos y provienen de entidades del Estado colombiano (datos.gov.co, IDEAM, DANE, UPRA) |

---

## 📦 Datasets Utilizados

### Total de Datasets: **10 fuentes integradas**

### 🇨🇴 Datasets de datos.gov.co (Datos Abiertos Colombia)

| # | Dataset | Fuente | Recurso ID | Descripción |
|---|---------|--------|-----------|-------------|
| 1 | **Producción Agrícola Municipal (EVA A04/A05)** | DANE — datos.gov.co | `uejq-wxrr` | Área sembrada, cosechada, producción (ton) y rendimiento (t/ha) por municipio, cultivo y año. 2019–2025 |
| 2 | **Catálogo de Estaciones IDEAM** | IDEAM — datos.gov.co | `hp9r-jxuu` | 991 estaciones con coordenadas, altitud, estado activo/inactivo y municipio asociado |
| 3 | **Precipitación IDEAM (series históricas)** | IDEAM — datos.gov.co | `s54a-sgyg` | Registros crudos de precipitación en milímetros por estación y período |
| 4 | **Variables Climáticas Combinadas IDEAM** | IDEAM — datos.gov.co | `57sv-p2fu` | Temperatura, humedad relativa y brillo solar por estación. 2018–2026 |
| 5 | **DIVIPOLA — División Político-Administrativa** | DANE — datos.gov.co | `gdxc-w37w` | Códigos oficiales de 5 dígitos para 1.122 municipios colombianos |

### 🌍 Datasets Externos

| # | Dataset | Fuente | URL/Acceso | Descripción |
|---|---------|--------|-----------|-------------|
| 6 | **Índice ENSO Mensual** | NOAA — Climate Prediction Center | API pública | Clasificación mensual del fenómeno ENSO (El Niño/La Niña/Neutro) 2000–2026 |
| 7 | **Precios Mayoristas Agrícolas (SIPSA)** | DANE — Microdatos | Catálogo 776 | Precios min/max/promedio por producto en centrales de abasto. 2013–2025 |
| 8 | **Aptitud Agrícola del Suelo (SIPRA)** | UPRA — GeoServer | WFS/GeoJSON | Clasificación del suelo: alta, moderada, marginal o no apta por cultivo y municipio |
| 9 | **Clima Diario Satelital MERRA-2** | NASA POWER | `power.larc.nasa.gov/api` | Precipitación y temperatura diaria por coordenadas geográficas. 2024 |
| 10 | **Precios de Insumos Agropecuarios** | DANE — SIPSA Insumos | Microdatos | Precios de fertilizantes, semillas, agroquímicos y combustibles por región. 2018–2025 |

---

## 📊 Variables Seleccionadas

### Variable Objetivo (Target)
- `rendimiento_t_ha` — Rendimiento del cultivo en toneladas por hectárea

### Variables Predictoras (Features del Modelo ML)

| Categoría | Variable | Descripción |
|-----------|----------|-------------|
| **Clima** | `lluvia_acumulada_anual` | Precipitación total anual en mm |
| **Clima** | `temp_promedio_anual` | Temperatura media anual en °C |
| **Clima** | `humedad_promedio_anual` | Humedad relativa promedio anual (%) |
| **Clima** | `brillo_solar_promedio` | Horas de brillo solar diario promedio |
| **Clima** | `lluvia_semestre_a` / `lluvia_semestre_b` | Lluvia por semestre A (Ene–Jun) y B (Jul–Dic) |
| **ENSO** | `spi_promedio` | Índice de Precipitación Estandarizado |
| **ENSO** | `anomalia_lluvia_pct` | Anomalía de precipitación (%) vs. normal histórica |
| **ENSO** | `prob_deficit` / `prob_exceso` | Probabilidad de déficit o exceso hídrico |
| **ENSO** | `es_anio_nino_int` | Bandera: ¿Es año El Niño? (0/1) |
| **Mercado** | `precio_promedio_cop_kg` | Precio mayorista promedio del cultivo (COP/kg) |
| **Insumos** | `precio_insumo_promedio` | Precio promedio de insumos agrícolas (COP) |
| **Suelos** | `clase_aptitud_score` | Aptitud del suelo: alta=3, moderada=2, marginal=1, no_apta=0 |
| **Territorio** | `id_municipio_enc` / `id_region` | Municipio y región natural codificados |
| **Lags** | `lluvia_acumulada_anual_lag1` / `_lag3` | Lluvia del año anterior y de hace 3 años |
| **Histórico** | `rendimiento_t_ha_hist_avg` | Rendimiento histórico promedio del municipio×cultivo |

**Total: ~35 features candidatas** por observación (fila = municipio × cultivo × año).

---

## 🔬 Tipo de Análisis

### 1. Análisis descriptivo — comparación de grupos
Tres comparaciones sobre datos reales, con supuestos realistas (`validate/anova_tests.py`, `validate/anova_robusto.py`):

| # | Pregunta | Factor |
|---|----------|--------|
| 1 | ¿Llueve diferente en El Niño, La Niña y Neutro? | Fase ENSO |
| 2 | ¿Hay estacionalidad de lluvias en Colombia? | Trimestre |
| 3 | ¿Llueve igual en Ibagué, Pasto y Villavicencio? (fuente externa NASA) | Municipio |

Cada prueba compara **una unidad independiente por mes** (no miles de lecturas estación-mes, que no son independientes), usa **ANOVA de Welch** y **Kruskal-Wallis**, reporta el **tamaño del efecto (η²)** y un post-hoc de **Mann-Whitney con corrección de Holm**.
Resultado: la **estacionalidad** tiene un efecto grande; el efecto de **ENSO** sobre la lluvia mensual es **pequeño** (p ≈ 0,03, η² ≈ 0,05; solo El Niño vs. Neutro se distingue); con solo 12 meses por ciudad, la prueba de NASA no distingue pares concluyentes. (La versión anterior trataba cada lectura como independiente y reportaba p < 0,001 en todo; eso sobrestimaba la evidencia. Se eliminó la prueba de precios de insumos por tipo, que comparaba unidades distintas.)

### 2. Análisis predictivo — regresión del rendimiento
- **Objetivo**: rendimiento (t/ha) por municipio × cultivo × año.
- **Modelo**: XGBoost que aprende la **desviación respecto al promedio histórico** del municipio × cultivo.
- **Evaluación honesta**: validación temporal **por año**, el último año con datos se reserva como año de prueba (no se usa para entrenar ni ajustar), y siempre se compara con una **línea base** (el promedio histórico). Solo se guardan predicciones **fuera de muestra**.

### 3. Alerta climática anticipada
El nivel de riesgo se define con un **índice por reglas** (no hay etiquetas históricas validadas). El modelo predice ese índice del **mes siguiente** con corte temporal y se compara con la persistencia ("el mes siguiente repite el actual").

---

## 🤖 Modelo Utilizado

| Aspecto | Detalle |
|---------|---------|
| Algoritmo | XGBoost Regressor (objetivo: error absoluto) sobre la desviación vs. la línea base |
| Ajuste | Optuna (TPE); número de pruebas configurable con `OPTUNA_TRIALS` (por defecto 60) |
| Validación | Ventana creciente **por año** (entrena con años anteriores, valida en el siguiente) |
| Prueba final | Último año con datos, fuera del entrenamiento y del ajuste |
| Intervalos | p10–p90 calibrados con los residuos reales de la validación (por cultivo cuando hay datos) |
| Explicabilidad | SHAP por predicción (top 3 factores) |
| Datos faltantes | Se dejan como NaN; nunca se rellenan con 0 |

---

## 📈 Resultados

Las métricas **no están escritas a mano**: cada entrenamiento las guarda en `model_version.metricas_json` y la web las lee (pestañas Inicio, Dashboards y Metodología, y `/api/modelo/metricas`).

Ejemplo de una corrida real con los datos de producción del DANE (2019–2025) **sin datos de clima cargados**: en el año de prueba 2025 el modelo obtuvo R² ≈ 0,87 y MAE ≈ 2,26 t/ha frente a MAE ≈ 2,34 t/ha de la línea base (mejora ≈ 3 %), con intervalos p10–p90 que contienen el valor real ≈ 83 % de las veces (esperado: 80 %). El R² es alto porque los cultivos tienen rendimientos muy distintos entre sí; por eso la comparación relevante es el MAE frente a la línea base. Al cargar el clima del IDEAM el resultado puede cambiar: es el que debes leer en tu base de datos.

### Cobertura de datos
Los valores de cobertura (municipios, cultivos, rango de años) se calculan en vivo desde la base de datos: ver `/api/impacto`. La fuente de producción (EVA, `uejq-wxrr`) trae datos **2019–2025**.

### Limitaciones conocidas
- La aptitud de suelo (UPRA/SIPRA) **no se está usando**: el servicio ArcGIS dejó de publicar las capas.
- El "SPI" es una anomalía estandarizada calculada con unos 8 años de clima (2018+), no el SPI clásico de 30 años.
- Los ajustes por escenario ENSO/lluvia del simulador son reglas fijas orientativas, no salidas del modelo.
- Los precios SIPSA cubren 36 productos frescos; solo se enlazan a cultivos de la EVA los que tienen equivalencia clara.

---

## 🚀 Impacto Potencial

| Actor | Beneficio |
|-------|-----------|
| **Productores rurales** | Decisiones de siembra informadas, reduciendo pérdidas por clima adverso |
| **Finagro / Bancóldex** | Mejoran la evaluación del riesgo agropecuario en crédito rural |
| **Gobernaciones y alcaldías** | Focalización de asistencia técnica en zonas de alto riesgo |
| **Ministerio de Agricultura** | Política pública basada en evidencia de datos |
| **Investigadores** | Base de datos abierta y reproducible para estudios agronómicos |
| **Alcance estimado** | **~500.000 productores** en municipios cubiertos |

---

## 💻 Solución en Producción (Demo en Vivo)

Para ver y probar la solución funcionando en tiempo real a través de los siguientes accesos:

**Aplicación Web / Producción:** [Visitar la solución en vivo](https://agroia-colombia.vercel.app)

**Documentación de la API:** [Explorar Power BI Integration](web/POWERBI_INTEGRATION.md)

---


### Documentación Técnica

| Documento | Descripción |
|-----------|-------------|
| [Arquitectura](docs/ARQUITECTURA.md) | Componentes, flujo de datos y decisiones de diseño (con diagrama) |
| [Diccionario de datos](docs/DICCIONARIO_DATOS.md) | Tablas y columnas de la base de datos (**generado** desde el esquema real) |
| [Operación](docs/OPERACION.md) | Migraciones, rol de solo lectura, alertas, imágenes Docker y CI |
| [Runbook de incidentes](docs/RUNBOOK.md) | Qué hacer cuando algo falla o los datos se atrasan |
| [Puesta en marcha de Precios](docs/PRECIOS_PUESTA_EN_MARCHA.md) | Supabase, Railway y Vercel paso a paso |
| [Contribuir](CONTRIBUTING.md) | Reglas del proyecto y flujo de trabajo |

La metodología, las métricas del modelo y los límites conocidos están en la propia aplicación (pestañas **Metodología** y **Datos**), leídos de la base de datos.

---

## ⚙️ Cómo Correr Localmente

**Con datos de ejemplo (sin descargar nada; requiere Docker):**

```powershell
.\scripts\tasks.ps1 setup    # venv + dependencias + Postgres 16 en Docker + migraciones + datos SINTÉTICOS
.\scripts\tasks.ps1 dev      # web en http://localhost:3000 contra esa base local
.\scripts\tasks.ps1 test     # ruff + pytest (incluye pruebas contra Postgres)
```

Los datos de ejemplo son inventados a propósito (solo sirven para ver la interfaz y probar); la web lo avisa en `/api/estado`.
`seed_dev.py` se niega a correr contra una base que no sea local.

**Con datos reales** (`.env` con tu base; ver [.env.example](.env.example)):

```bash
python -m load.migrate                       # aplica las migraciones pendientes (migrations/)
python run_pipeline.py --mode all --once     # ETL completo: core + extended + modelos
python run_pipeline.py --mode precios --once # ingesta diaria de precios SIPSA
python run_pipeline.py --mode salud --once   # solo revisa frescura y avisa por webhook
python -m validate.anova_tests --export-web  # (opcional) regenera gráficas ANOVA
```

Operación, seguridad de la base (rol de solo lectura, RLS), alertas y CI: **[docs/OPERACION.md](docs/OPERACION.md)** · cómo contribuir: **[CONTRIBUTING.md](CONTRIBUTING.md)**.

---

## 💲 Precios mayoristas diarios (SIPSA – DANE)

Sección **Precios** de la web: precio por kilo de 36 frutas, verduras, tubérculos y plátanos en ~24 mercados
mayoristas de 20 departamentos (por ejemplo, papa criolla en Pasto), con variación diaria y semanal, historial
desde 2020, informe diario y pronóstico a 1–10 días hábiles.

**Qué es y qué no es**
- Son precios **mayoristas** (no de venta al consumidor). No incluye granos, carnes, lácteos, huevos ni café.
- DANE publica **una vez por día hábil** (hacia el mediodía). "Cada hora" significa que el sistema revisa cada hora
  si hay dato nuevo; la página muestra la fecha del dato y la hora de la última revisión.
- No todos los mercados reportan todos los productos: por ejemplo, Pasto dejó de reportar papa negra en 2020.

**Fuentes**: Excel diario `anex-SIPSADiario-DDmmmAAAA.xlsx` (16 mercados, sondeo horario barato) y servicio SOAP 1.2
`appweb.dane.gov.co/sipsaWS` (historial completo con mín/máx y los demás mercados; ~300 MB, sin filtros de fecha).

```bash
python run_prices.py --mode init        # aplica las migraciones pendientes (migrations/)
python run_prices.py --mode backfill    # historial completo por SOAP (una vez)
python run_prices.py --mode hourly      # sondeo horario + pronóstico + informe (cron de Railway: 0 * * * *)
python run_prices.py --mode forecast    # reentrena con backtest y pronostica
python run_prices.py --mode informe     # regenera el informe del último día
```

📋 **Guía de puesta en marcha paso a paso (Supabase, Railway, Vercel): [docs/PRECIOS_PUESTA_EN_MARCHA.md](docs/PRECIOS_PUESTA_EN_MARCHA.md)**

El cron horario se despliega como un segundo servicio de Railway con `railway.precios.json`
(`startCommand: python run_prices.py --mode hourly`). Las rutas web están en `web/app/api/precios/*`
y la página en `web/app/components/PagePrecios.jsx`.

**Pronóstico**: XGBoost global sobre el cambio logarítmico a h días hábiles, con backtest de origen rodante ordenado
por fecha. Solo se publica como "modelo" para un producto si supera en el backtest a la línea base
("el precio de hoy no cambia"); si no, se muestra la línea base con confianza baja. Las métricas quedan en
`model_version.metricas_json`.

---

*Proyecto desarrollado en el marco del curso de Ciencia de Datos — 2026*
