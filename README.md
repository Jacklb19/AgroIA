# AgroIA Colombia — Dashboard de Inteligencia Agro-Climática

Aplicación web que integra datos climáticos, precios de insumos y producción agrícola de Colombia para predecir rendimientos de cultivos y analizar factores que los afectan.

---

## ¿Qué hace la aplicación?

| Sección | Qué hace |
|---|---|
| **Inicio** | Resumen general con indicadores clave, mapa de riesgo territorial y alertas ENSO |
| **Dashboards** | Gráficos interactivos de producción agrícola, precios y clima por municipio |
| **Predicción** | Formulario para estimar el rendimiento de un cultivo dado municipio, año, fase ENSO y lluvia esperada. Usa un modelo XGBoost entrenado con datos históricos |
| **Asistente IA** | Chat con inteligencia artificial que responde preguntas sobre clima, cultivos e insumos |
| **Metodología** | Documentación del pipeline de datos, fuentes utilizadas, métricas del modelo y **análisis estadístico ANOVA** |
| **Impacto** | Alcance del proyecto: municipios cubiertos, cultivos analizados, productores potenciales |

---

## Análisis ANOVA (pestaña Metodología → scroll al final)

Se implementaron 4 pruebas estadísticas ANOVA de una vía para confirmar con evidencia matemática las relaciones entre variables climáticas y agro-económicas:

| # | Pregunta | Resultado |
|---|---|---|
| 1 | ¿Llueve diferente durante El Niño, La Niña y años Neutros? | ★★★ Significativo |
| 2 | ¿Los fertilizantes, semillas y agroquímicos tienen precios distintos? | ★★★ Significativo |
| 3 | ¿Hay épocas del año con más lluvia que otras en Colombia? | ★★★ Significativo |
| 4 | ¿Llueve igual en Ibagué, Pasto y Villavicencio? (datos NASA) | ★★★ Significativo |

Cada prueba incluye: test de Levene, estadístico F, p-valor y análisis post-hoc Tukey HSD. Los boxplots muestran la distribución real de los datos con medianas anotadas y escalas legibles.

---

## Fuentes de datos

- **IDEAM** — Series climáticas de 991 estaciones terrestres (2015–2026)
- **NOAA** — Índice ENSO mensual (El Niño / La Niña / Neutro)
- **DANE · SIPSA** — Precios mayoristas e índice de insumos agrícolas
- **UPRA · SIPRA** — Aptitud agrícola del suelo por municipio
- **NASA POWER MERRA-2** — Precipitación y temperatura satelital diaria (2024)

---

## Tecnologías

| Capa | Tecnología |
|---|---|
| Frontend | Next.js 14 + React 18 (desplegado en Vercel) |
| Modelo | XGBoost con tuning bayesiano (Optuna, 200 trials) |
| Estadística | Python · scipy · statsmodels · pandas |
| Base de datos | PostgreSQL con esquema estrella (star schema) |
| Visualización | SVG puro en React + Matplotlib para gráficos ANOVA |

---

## Cómo correr localmente

```bash
# 1. Instalar dependencias del frontend
cd web && npm install

# 2. Iniciar servidor de desarrollo
npm run dev
# → http://localhost:3000

# 3. (Opcional) Regenerar gráficas ANOVA
cd .. && python -m validate.anova_tests --verbose
```
