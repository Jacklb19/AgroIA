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
| 1 | **Producción Agrícola Municipal (EVA A04/A05)** | DANE — datos.gov.co | `uejq-wxrr` | Área sembrada, cosechada, producción (ton) y rendimiento (t/ha) por municipio, cultivo y año. 2007–2025 |
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

### 1. Análisis Descriptivo — Estadística Inferencial (ANOVA)
Se realizaron **4 pruebas ANOVA de una vía** con sus respectivos tests post-hoc Tukey HSD:

| # | Hipótesis | Variable | Factor | p-valor |
|---|-----------|----------|--------|---------|
| 1 | ¿Llueve diferente en El Niño, La Niña y Neutro? | Precipitación mm | Fase ENSO | **< 0.001 ★★★** |
| 2 | ¿Los insumos tienen precios distintos por categoría? | Precio COP | Tipo insumo | **< 0.001 ★★★** |
| 3 | ¿Hay estacionalidad de lluvias en Colombia? | Precipitación mm | Trimestre | **< 0.001 ★★★** |
| 4 | ¿Llueve igual en Ibagué, Pasto y Villavicencio? | Precipitación mm (NASA) | Municipio | **< 0.001 ★★★** |

### 2. Análisis Predictivo — Regresión
- **Objetivo**: Predecir el rendimiento agrícola (t/ha) de cualquier cultivo en cualquier municipio.
- **Tipo**: Regresión continua (variable de salida numérica: toneladas por hectárea).

---

## 🤖 Modelo Utilizado

### Algoritmo: **XGBoost Regressor** con Optimización Bayesiana (Optuna)

| Parámetro | Valor |
|-----------|-------|
| Algoritmo | XGBoost Regressor |
| Optimización | Optuna — TPE Sampler Bayesiano |
| Trials Optuna | **200 experimentos** |
| N° estimadores | 400–1.500 (ajustado automáticamente) |
| Profundidad máxima | 4–10 niveles |
| Tasa de aprendizaje | 0.01–0.15 (log-uniforme) |
| Validación cruzada | TimeSeriesSplit — 5 folds temporales |
| Conjunto de prueba | Hold-out temporal: últimos 20% de años |
| Explicabilidad | **SHAP** — valores Shapley por predicción |

---

## 📈 Resultados Clave

### Métricas del Modelo de Rendimiento

| Métrica | Descripción | Resultado |
|---------|-------------|-----------|
| **R²** | Coeficiente de determinación | > 0.80 |
| **MAE** | Error Absoluto Medio (t/ha) | < 0.50 t/ha |
| **RMSE** | Raíz del Error Cuadrático Medio | < 0.80 t/ha |

### Cobertura del Sistema

| Indicador | Valor |
|-----------|-------|
| Estaciones climáticas IDEAM | **991** |
| Municipios cubiertos | **> 1.100** |
| Cultivos analizados | **> 50** |
| Período de producción | **2007–2025** |
| Período de clima | **2018–2026** |
| Tablas en base de datos | **18** |

### Resultados ANOVA

Todas las **4 pruebas ANOVA** arrojaron **p < 0.001**, confirmando con evidencia estadística rigurosa que el clima (ENSO, estacionalidad y geografía) tiene un impacto diferencial y significativo sobre los ciclos agrícolas en Colombia.

---

## 🧠 Interpretación

- **El modelo XGBoost** identifica la lluvia acumulada anual, la temperatura y la aptitud del suelo como los predictores más determinantes del rendimiento agrícola.
- Los **lags temporales** capturan efectos de largo plazo en cultivos permanentes (café, plátano, palma), donde las condiciones climáticas de años anteriores impactan la cosecha actual.
- Los **valores SHAP** permiten explicar cada predicción individual: el sistema puede indicar, por ejemplo, que "el déficit hídrico registrado durante El Niño 2024 redujo el rendimiento predicho en 0.3 t/ha para el maíz en Córdoba".
- El **análisis ANOVA** confirma científicamente que los datos justifican tratar por separado cada fase ENSO, región natural y semestre del año al modelar el rendimiento.
- Durante **años El Niño**, el modelo anticipa caídas de rendimiento de hasta 25% en cultivos transitorios de las regiones Andina y Caribe.

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
| [Planteamiento del Problema](docs/planteamiento_problema.md) | Contexto, problema y objetivos del proyecto |
| [Marco Metodológico](docs/marco_metodologico.md) | Pipeline ETL, metodología ML y protocolo estadístico |
| [Fuentes de Datos](docs/fuentes_datos.md) | Descripción completa de cada dataset |
| [Diccionario de Datos](docs/diccionario_datos.md) | Definición de cada variable en la base de datos |
| [Arquitectura del Sistema](docs/architecture.md) | Diagrama e infraestructura del sistema |
| [Guía de Validación](docs/validation_guide.md) | Cómo reproducir resultados y pruebas ANOVA |
| [Conclusiones](docs/conclusiones.md) | Hallazgos, limitaciones y trabajo futuro |

---

## ⚙️ Cómo Correr Localmente

```bash
# 1. Instalar dependencias del frontend
cd web && npm install

# 2. Iniciar servidor de desarrollo
npm run dev
# → http://localhost:3000

# 3. (Opcional) Regenerar gráficas ANOVA
cd .. && python -m validate.anova_tests --verbose

# 4. (Opcional) Ejecutar pipeline ETL completo
python run_pipeline.py --mode all --once
```

---

*Proyecto desarrollado en el marco del curso de Ciencia de Datos — 2026*
