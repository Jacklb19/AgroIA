# Diccionario de datos

> **Archivo generado** por `python scripts/gen_data_dictionary.py` a partir del esquema real (migraciones aplicadas).
> No lo edites a mano: cambia las migraciones o las descripciones del script y vuelve a generarlo.

27 tablas y 5 vistas. Convenciones: `dim_*` dimensiones, `fact_*` hechos, `pred_*` salidas de modelos, `v_*` vistas para Power BI y la web.

| Objeto | Propósito |
|---|---|
| `chat_message` | Mensajes de cada sesión del asistente. |
| `chat_rate` | Contadores diarios del asistente (por IP con hash y global) para limitar el gasto. |
| `chat_session` | Sesiones del asistente conversacional. |
| `dim_central_abastos` | Mercados mayoristas (centrales de abasto) con su departamento. |
| `dim_cultivo` | Cultivos de la Evaluación Agropecuaria Municipal (nombre normalizado sin tildes). |
| `dim_estacion_ideam` | Estaciones meteorológicas del IDEAM asignadas a un municipio. |
| `dim_municipio` | Municipios (código DIVIPOLA de 5 dígitos), con departamento, región y centroide. |
| `dim_producto_precio` | Productos con precio mayorista SIPSA; `id_cultivo` los enlaza con la EVA cuando hay equivalencia clara. |
| `dim_region_natural` | Regiones naturales de Colombia (Andina, Caribe, Pacífico, Orinoquía, Amazonía). |
| `dim_tiempo` | Un registro por mes (primer día); marca los años El Niño derivados del ONI. |
| `extraction_report` | Último reporte de completitud de cada fuente al extraerla. |
| `fact_alerta_enso` | Fase ENSO por trimestre y región, con ONI, SPI y anomalía de precipitación. |
| `fact_aptitud_suelo` | Clase de aptitud de suelo por municipio × cultivo (UPRA/SIPRA; hoy sin fuente activa). |
| `fact_censo_agropecuario` | Uso del suelo por municipio del Censo Nacional Agropecuario (DANE). |
| `fact_clima_mensual` | Clima mensual por estación IDEAM: lluvia, temperatura, humedad, brillo solar. |
| `fact_precio_diario` | Precio mayorista diario por mercado × producto (SIPSA): promedio, mínimo y máximo por kilo. |
| `fact_precios_insumos` | Precios de insumos agrícolas (IPIA, DANE). |
| `fact_precios_mayoristas` | Precios mayoristas mensuales por mercado × cultivo (tabla histórica anterior a la diaria). |
| `fact_produccion_agricola` | Producción anual por municipio × cultivo: áreas, toneladas y rendimiento (t/ha). Fuente: EVA (datos.gov.co). |
| `informe_precio_diario` | Informe diario de precios (JSON) generado tras cada carga. |
| `ingest_run` | Bitácora de ejecuciones: cada etapa del pipeline y cada job de precios (estado, filas, fecha del dato). |
| `model_version` | Versiones de modelos entrenados, con métricas en JSON; `activo` marca la vigente. |
| `pred_alerta_climatica` | Nivel de riesgo climático del mes siguiente por municipio (índice por reglas + modelo). |
| `pred_precio` | Pronóstico de precios a 1–10 días hábiles con su confianza. |
| `pred_rendimiento` | Predicciones de rendimiento fuera de muestra por municipio × cultivo × año, con intervalo p10–p90 y SHAP. |
| `quality_check_run` | Resultados históricos de los controles de calidad de datos. |
| `schema_migrations` | Migraciones de esquema aplicadas y su checksum. |
| `v_alertas_climaticas` | Vista para Power BI: alertas climáticas activas. |
| `v_dashboard_agro` | Vista para Power BI: producción anual con clima anual del municipio. |
| `v_monitor_climatico` | Vista para Power BI: clima mensual con fase ENSO. |
| `v_precio_actual` | Último precio por mercado × producto con variación diaria y de 7 días (la usa la pestaña Precios). |
| `v_predicciones_modelo` | Vista para Power BI: predicciones frente a rendimiento real y metadatos del modelo. |

## Dimensiones

### `dim_central_abastos`

Mercados mayoristas (centrales de abasto) con su departamento.

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id_central` | int | no | autoincremental |
| `nombre_central` | varchar(150) | no |  |
| `ciudad` | varchar(100) | no |  |
| `id_municipio` | char(5) | sí |  |
| `id_departamento` | char(2) | sí |  |
| `nombre_departamento` | varchar(100) | sí |  |

Restricciones:
- Único: `UNIQUE (nombre_central, ciudad)`
- Clave primaria: `PRIMARY KEY (id_central)`
- Clave foránea: `FOREIGN KEY (id_municipio) REFERENCES dim_municipio(id_municipio)`

### `dim_cultivo`

Cultivos de la Evaluación Agropecuaria Municipal (nombre normalizado sin tildes).

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id_cultivo` | int | no | autoincremental |
| `nombre_cultivo` | varchar(100) | no |  |
| `nombre_normalizado` | varchar(100) | no |  |
| `tipo_ciclo` | varchar(20) | sí |  |
| `familia_botanica` | varchar(100) | sí |  |

Restricciones:
- Único: `UNIQUE (nombre_normalizado)`
- Clave primaria: `PRIMARY KEY (id_cultivo)`

### `dim_estacion_ideam`

Estaciones meteorológicas del IDEAM asignadas a un municipio.

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id_estacion` | varchar(20) | no |  |
| `nombre_estacion` | varchar(150) | sí |  |
| `tipo_estacion` | varchar(50) | sí |  |
| `latitud` | double | sí |  |
| `longitud` | double | sí |  |
| `altitud_msnm` | double | sí |  |
| `id_municipio` | char(5) | sí |  |
| `estado_activa` | bool | sí | true |

Restricciones:
- Clave primaria: `PRIMARY KEY (id_estacion)`
- Clave foránea: `FOREIGN KEY (id_municipio) REFERENCES dim_municipio(id_municipio)`

### `dim_municipio`

Municipios (código DIVIPOLA de 5 dígitos), con departamento, región y centroide.

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id_municipio` | char(5) | no |  |
| `nombre_municipio` | varchar(100) | no |  |
| `id_departamento` | char(2) | no |  |
| `nombre_departamento` | varchar(100) | no |  |
| `id_region` | int | sí |  |
| `latitud_centroide` | double | sí |  |
| `longitud_centroide` | double | sí |  |

Restricciones:
- Clave primaria: `PRIMARY KEY (id_municipio)`
- Clave foránea: `FOREIGN KEY (id_region) REFERENCES dim_region_natural(id_region)`

### `dim_producto_precio`

Productos con precio mayorista SIPSA; `id_cultivo` los enlaza con la EVA cuando hay equivalencia clara.

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id_producto` | int | no | autoincremental |
| `nombre` | varchar(100) | no |  |
| `nombre_normalizado` | varchar(100) | no |  |
| `grupo` | varchar(60) | sí |  |
| `id_cultivo` | int | sí |  |

Restricciones:
- Único: `UNIQUE (nombre_normalizado)`
- Clave primaria: `PRIMARY KEY (id_producto)`
- Clave foránea: `FOREIGN KEY (id_cultivo) REFERENCES dim_cultivo(id_cultivo)`

### `dim_region_natural`

Regiones naturales de Colombia (Andina, Caribe, Pacífico, Orinoquía, Amazonía).

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id_region` | int | no | autoincremental |
| `nombre_region` | varchar(50) | no |  |

Restricciones:
- Único: `UNIQUE (nombre_region)`
- Clave primaria: `PRIMARY KEY (id_region)`

### `dim_tiempo`

Un registro por mes (primer día); marca los años El Niño derivados del ONI.

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id_tiempo` | int | no | autoincremental |
| `fecha` | date | no |  |
| `anio` | smallint | no |  |
| `mes` | smallint | no |  |
| `trimestre` | smallint | no |  |
| `semestre` | char(1) | no |  |
| `nombre_mes` | varchar(20) | no |  |
| `es_anio_nino` | bool | no | false |

Restricciones:
- Único: `UNIQUE (fecha)`
- Clave primaria: `PRIMARY KEY (id_tiempo)`

## Hechos

### `fact_alerta_enso`

Fase ENSO por trimestre y región, con ONI, SPI y anomalía de precipitación.

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | int | no | autoincremental |
| `id_tiempo` | int | no |  |
| `id_region` | int | no |  |
| `fase_enso` | varchar(20) | sí |  |
| `indice_spi` | double | sí |  |
| `anomalia_precipitacion_pct` | double | sí |  |
| `probabilidad_deficit_hidrico` | double | sí |  |
| `probabilidad_exceso_hidrico` | double | sí |  |
| `fuente_origen` | varchar(100) | sí |  |
| `es_sintetico` | bool | no | false |
| `indice_oni` | double | sí |  |

Restricciones:
- Único: `UNIQUE (id_tiempo, id_region)`
- Clave primaria: `PRIMARY KEY (id)`
- Clave foránea: `FOREIGN KEY (id_region) REFERENCES dim_region_natural(id_region)`
- Clave foránea: `FOREIGN KEY (id_tiempo) REFERENCES dim_tiempo(id_tiempo)`

### `fact_aptitud_suelo`

Clase de aptitud de suelo por municipio × cultivo (UPRA/SIPRA; hoy sin fuente activa).

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | int | no | autoincremental |
| `id_municipio` | char(5) | no |  |
| `id_cultivo` | int | sí |  |
| `clase_aptitud` | varchar(20) | sí |  |

Restricciones:
- Único: `UNIQUE (id_municipio, id_cultivo)`
- Clave primaria: `PRIMARY KEY (id)`
- Clave foránea: `FOREIGN KEY (id_cultivo) REFERENCES dim_cultivo(id_cultivo)`
- Clave foránea: `FOREIGN KEY (id_municipio) REFERENCES dim_municipio(id_municipio)`

### `fact_censo_agropecuario`

Uso del suelo por municipio del Censo Nacional Agropecuario (DANE).

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | int | no | autoincremental |
| `id_municipio` | char(5) | no |  |
| `anio_censo` | smallint | no |  |
| `area_cultivos_permanentes_ha` | double | sí |  |
| `area_cultivos_transitorios_ha` | double | sí |  |
| `area_pastos_ha` | double | sí |  |
| `area_rastrojo_ha` | double | sí |  |
| `area_agricola_ha` | double | sí |  |
| `area_infraestructura_ha` | double | sí |  |

Restricciones:
- Único: `UNIQUE (id_municipio, anio_censo)`
- Clave primaria: `PRIMARY KEY (id)`
- Clave foránea: `FOREIGN KEY (id_municipio) REFERENCES dim_municipio(id_municipio)`

### `fact_clima_mensual`

Clima mensual por estación IDEAM: lluvia, temperatura, humedad, brillo solar.

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | int | no | autoincremental |
| `id_estacion` | varchar(20) | no |  |
| `id_municipio` | char(5) | no |  |
| `id_tiempo` | int | no |  |
| `precipitacion_mm` | double | sí |  |
| `temperatura_media_c` | double | sí |  |
| `temperatura_max_c` | double | sí |  |
| `temperatura_min_c` | double | sí |  |
| `humedad_relativa_pct` | double | sí |  |
| `brillo_solar_horas_dia` | double | sí |  |

Restricciones:
- Único: `UNIQUE (id_estacion, id_tiempo)`
- Clave primaria: `PRIMARY KEY (id)`
- Clave foránea: `FOREIGN KEY (id_estacion) REFERENCES dim_estacion_ideam(id_estacion)`
- Clave foránea: `FOREIGN KEY (id_municipio) REFERENCES dim_municipio(id_municipio)`
- Clave foránea: `FOREIGN KEY (id_tiempo) REFERENCES dim_tiempo(id_tiempo)`

### `fact_precio_diario`

Precio mayorista diario por mercado × producto (SIPSA): promedio, mínimo y máximo por kilo.

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | bigint | no | autoincremental |
| `id_central` | int | no |  |
| `id_producto` | int | no |  |
| `fecha` | date | no |  |
| `precio_min_kg` | double | sí |  |
| `precio_max_kg` | double | sí |  |
| `precio_prom_kg` | double | no |  |
| `fuente` | varchar(10) | no | 'soap'::character varying |
| `ingested_at` | timestamptz | no | now() |

Restricciones:
- Único: `UNIQUE (id_central, id_producto, fecha)`
- Clave primaria: `PRIMARY KEY (id)`
- Clave foránea: `FOREIGN KEY (id_central) REFERENCES dim_central_abastos(id_central)`
- Clave foránea: `FOREIGN KEY (id_producto) REFERENCES dim_producto_precio(id_producto)`

### `fact_precios_insumos`

Precios de insumos agrícolas (IPIA, DANE).

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | int | no | autoincremental |
| `id_tiempo` | int | no |  |
| `tipo_insumo` | varchar(50) | sí |  |
| `nombre_insumo` | varchar(100) | sí |  |
| `precio_cop_unidad` | double | sí |  |
| `unidad_medida` | varchar(20) | sí |  |
| `id_region` | int | sí |  |
| `fuente_origen` | varchar(100) | sí |  |
| `es_sintetico` | bool | no | false |

Restricciones:
- Único: `UNIQUE (id_tiempo, tipo_insumo, nombre_insumo, id_region)`
- Clave primaria: `PRIMARY KEY (id)`
- Clave foránea: `FOREIGN KEY (id_region) REFERENCES dim_region_natural(id_region)`
- Clave foránea: `FOREIGN KEY (id_tiempo) REFERENCES dim_tiempo(id_tiempo)`

### `fact_precios_mayoristas`

Precios mayoristas mensuales por mercado × cultivo (tabla histórica anterior a la diaria).

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | int | no | autoincremental |
| `id_central` | int | no |  |
| `id_cultivo` | int | no |  |
| `id_tiempo` | int | no |  |
| `precio_min_cop_kg` | double | sí |  |
| `precio_max_cop_kg` | double | sí |  |
| `precio_promedio_cop_kg` | double | sí |  |
| `volumen_abastecimiento_ton` | double | sí |  |

Restricciones:
- Único: `UNIQUE (id_central, id_cultivo, id_tiempo)`
- Clave primaria: `PRIMARY KEY (id)`
- Clave foránea: `FOREIGN KEY (id_central) REFERENCES dim_central_abastos(id_central)`
- Clave foránea: `FOREIGN KEY (id_cultivo) REFERENCES dim_cultivo(id_cultivo)`
- Clave foránea: `FOREIGN KEY (id_tiempo) REFERENCES dim_tiempo(id_tiempo)`

### `fact_produccion_agricola`

Producción anual por municipio × cultivo: áreas, toneladas y rendimiento (t/ha). Fuente: EVA (datos.gov.co).

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | int | no | autoincremental |
| `id_municipio` | char(5) | no |  |
| `id_cultivo` | int | no |  |
| `id_tiempo` | int | no |  |
| `area_sembrada_ha` | double | sí |  |
| `area_cosechada_ha` | double | sí |  |
| `produccion_total_ton` | double | sí |  |
| `rendimiento_t_ha` | double | sí |  |
| `fuente_origen` | varchar(50) | sí |  |

Restricciones:
- Único: `UNIQUE (id_municipio, id_cultivo, id_tiempo)`
- Clave primaria: `PRIMARY KEY (id)`
- Clave foránea: `FOREIGN KEY (id_cultivo) REFERENCES dim_cultivo(id_cultivo)`
- Clave foránea: `FOREIGN KEY (id_municipio) REFERENCES dim_municipio(id_municipio)`
- Clave foránea: `FOREIGN KEY (id_tiempo) REFERENCES dim_tiempo(id_tiempo)`

## Modelos y predicciones

### `informe_precio_diario`

Informe diario de precios (JSON) generado tras cada carga.

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `fecha` | date | no |  |
| `payload` | jsonb | no |  |
| `generado_at` | timestamptz | no | now() |

Restricciones:
- Clave primaria: `PRIMARY KEY (fecha)`

### `model_version`

Versiones de modelos entrenados, con métricas en JSON; `activo` marca la vigente.

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id_version` | int | no | autoincremental |
| `nombre_modelo` | varchar(100) | no |  |
| `fecha_entrenamiento` | timestamptz | sí | now() |
| `metricas_json` | jsonb | sí |  |
| `activo` | bool | no | false |

Restricciones:
- Clave primaria: `PRIMARY KEY (id_version)`

### `pred_alerta_climatica`

Nivel de riesgo climático del mes siguiente por municipio (índice por reglas + modelo).

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | int | no | autoincremental |
| `id_municipio` | char(5) | no |  |
| `id_tiempo` | int | no |  |
| `nivel_riesgo` | varchar(10) | sí |  |
| `tipo_evento` | varchar(30) | sí |  |
| `score_probabilidad` | double | sí |  |
| `descripcion_generada` | text | sí |  |
| `activa` | bool | sí | true |
| `id_version` | int | sí |  |

Restricciones:
- Único: `UNIQUE (id_municipio, id_tiempo)`
- Clave primaria: `PRIMARY KEY (id)`
- Clave foránea: `FOREIGN KEY (id_municipio) REFERENCES dim_municipio(id_municipio)`
- Clave foránea: `FOREIGN KEY (id_tiempo) REFERENCES dim_tiempo(id_tiempo)`
- Clave foránea: `FOREIGN KEY (id_version) REFERENCES model_version(id_version)`

### `pred_precio`

Pronóstico de precios a 1–10 días hábiles con su confianza.

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | bigint | no | autoincremental |
| `id_central` | int | no |  |
| `id_producto` | int | no |  |
| `fecha_objetivo` | date | no |  |
| `horizonte_dias` | smallint | no |  |
| `precio_pred_kg` | double | no |  |
| `p10_kg` | double | sí |  |
| `p90_kg` | double | sí |  |
| `metodo` | varchar(30) | no |  |
| `confianza` | varchar(10) | no | 'media'::character varying |
| `id_version` | int | sí |  |
| `generado_at` | timestamptz | no | now() |

Restricciones:
- Único: `UNIQUE (id_central, id_producto, fecha_objetivo)`
- Clave primaria: `PRIMARY KEY (id)`
- Clave foránea: `FOREIGN KEY (id_central) REFERENCES dim_central_abastos(id_central)`
- Clave foránea: `FOREIGN KEY (id_producto) REFERENCES dim_producto_precio(id_producto)`
- Clave foránea: `FOREIGN KEY (id_version) REFERENCES model_version(id_version)`

### `pred_rendimiento`

Predicciones de rendimiento fuera de muestra por municipio × cultivo × año, con intervalo p10–p90 y SHAP.

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | int | no | autoincremental |
| `id_municipio` | char(5) | no |  |
| `id_cultivo` | int | no |  |
| `id_tiempo` | int | no |  |
| `rendimiento_predicho_t_ha` | double | sí |  |
| `intervalo_confianza_inferior` | double | sí |  |
| `intervalo_confianza_superior` | double | sí |  |
| `id_version` | int | sí |  |
| `shap_top` | jsonb | sí |  |
| `es_anomalia` | bool | sí | false |
| `anomalia_score` | numeric | sí |  |
| `es_holdout` | bool | no | false |

Restricciones:
- Único: `UNIQUE (id_municipio, id_cultivo, id_tiempo)`
- Clave primaria: `PRIMARY KEY (id)`
- Clave foránea: `FOREIGN KEY (id_cultivo) REFERENCES dim_cultivo(id_cultivo)`
- Clave foránea: `FOREIGN KEY (id_municipio) REFERENCES dim_municipio(id_municipio)`
- Clave foránea: `FOREIGN KEY (id_tiempo) REFERENCES dim_tiempo(id_tiempo)`
- Clave foránea: `FOREIGN KEY (id_version) REFERENCES model_version(id_version)`

## Operación y observabilidad

### `chat_message`

Mensajes de cada sesión del asistente.

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | int | no | autoincremental |
| `id_session` | uuid | no |  |
| `role` | varchar(15) | no |  |
| `content` | text | sí |  |
| `metadata` | jsonb | sí |  |
| `creada_at` | timestamptz | no | now() |

Restricciones:
- Clave primaria: `PRIMARY KEY (id)`
- Clave foránea: `FOREIGN KEY (id_session) REFERENCES chat_session(id_session) ON DELETE CASCADE`

### `chat_rate`

Contadores diarios del asistente (por IP con hash y global) para limitar el gasto.

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `clave` | text | no |  |
| `dia` | date | no |  |
| `n` | int | no | 0 |

Restricciones:
- Clave primaria: `PRIMARY KEY (clave, dia)`

### `chat_session`

Sesiones del asistente conversacional.

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id_session` | uuid | no |  |
| `user_label` | varchar(120) | sí |  |
| `creada_at` | timestamptz | no | now() |
| `ultima_at` | timestamptz | no | now() |

Restricciones:
- Clave primaria: `PRIMARY KEY (id_session)`

### `extraction_report`

Último reporte de completitud de cada fuente al extraerla.

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `fuente` | varchar(100) | no |  |
| `uri` | text | sí |  |
| `filas` | int | sí |  |
| `columnas` | int | sí |  |
| `duplicados` | int | sí |  |
| `completitud_pct` | jsonb | sí |  |
| `extraido_at` | timestamptz | sí |  |
| `sincronizado_at` | timestamptz | no | now() |

Restricciones:
- Clave primaria: `PRIMARY KEY (fuente)`

### `ingest_run`

Bitácora de ejecuciones: cada etapa del pipeline y cada job de precios (estado, filas, fecha del dato).

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | int | no | autoincremental |
| `fuente` | varchar(30) | no |  |
| `started_at` | timestamptz | no | now() |
| `finished_at` | timestamptz | sí |  |
| `status` | varchar(20) | no | 'running'::character varying |
| `filas_nuevas` | int | sí |  |
| `fecha_dato_max` | date | sí |  |
| `source_last_modified` | timestamptz | sí |  |
| `source_ref` | varchar(200) | sí |  |
| `error` | text | sí |  |

Restricciones:
- Clave primaria: `PRIMARY KEY (id)`

### `quality_check_run`

Resultados históricos de los controles de calidad de datos.

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | bigint | no | autoincremental |
| `ejecutado_at` | timestamptz | no | now() |
| `indicador` | varchar(80) | no |  |
| `descripcion` | text | sí |  |
| `valor` | double | sí |  |
| `estado` | varchar(12) | no |  |

Restricciones:
- Clave primaria: `PRIMARY KEY (id)`

### `schema_migrations`

Migraciones de esquema aplicadas y su checksum.

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `version` | text | no |  |
| `archivo` | text | no |  |
| `checksum` | text | no |  |
| `repetible` | bool | no | false |
| `aplicada_at` | timestamptz | no | now() |

Restricciones:
- Clave primaria: `PRIMARY KEY (version)`

## Vistas

### `v_alertas_climaticas`

Vista para Power BI: alertas climáticas activas.

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `codigo_divipola` | char(5) | sí |  |
| `nombre_municipio` | varchar(100) | sí |  |
| `nombre_departamento` | varchar(100) | sí |  |
| `nombre_region` | varchar(50) | sí |  |
| `latitud_centroide` | double | sí |  |
| `longitud_centroide` | double | sí |  |
| `anio` | smallint | sí |  |
| `mes` | smallint | sí |  |
| `nombre_mes` | varchar(20) | sí |  |
| `nivel_riesgo` | varchar(10) | sí |  |
| `tipo_evento` | varchar(30) | sí |  |
| `score_probabilidad` | double | sí |  |
| `descripcion_generada` | text | sí |  |
| `nombre_modelo` | varchar(100) | sí |  |

### `v_dashboard_agro`

Vista para Power BI: producción anual con clima anual del municipio.

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `codigo_divipola` | char(5) | sí |  |
| `nombre_municipio` | varchar(100) | sí |  |
| `nombre_departamento` | varchar(100) | sí |  |
| `nombre_region` | varchar(50) | sí |  |
| `latitud_centroide` | double | sí |  |
| `longitud_centroide` | double | sí |  |
| `nombre_cultivo` | varchar(100) | sí |  |
| `tipo_ciclo` | varchar(20) | sí |  |
| `anio` | smallint | sí |  |
| `area_sembrada_ha` | double | sí |  |
| `area_cosechada_ha` | double | sí |  |
| `produccion_total_ton` | double | sí |  |
| `rendimiento_t_ha` | double | sí |  |
| `precipitacion_mm_prom` | double | sí |  |
| `precipitacion_mm_total` | double | sí |  |
| `temperatura_media_c` | double | sí |  |
| `temperatura_max_c` | double | sí |  |
| `temperatura_min_c` | double | sí |  |
| `humedad_relativa_pct` | double | sí |  |
| `brillo_solar_horas_dia` | double | sí |  |

### `v_monitor_climatico`

Vista para Power BI: clima mensual con fase ENSO.

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `codigo_divipola` | char(5) | sí |  |
| `nombre_municipio` | varchar(100) | sí |  |
| `nombre_departamento` | varchar(100) | sí |  |
| `nombre_region` | varchar(50) | sí |  |
| `latitud_centroide` | double | sí |  |
| `longitud_centroide` | double | sí |  |
| `nombre_estacion` | varchar(150) | sí |  |
| `anio` | smallint | sí |  |
| `mes` | smallint | sí |  |
| `nombre_mes` | varchar(20) | sí |  |
| `trimestre` | smallint | sí |  |
| `precipitacion_mm` | double | sí |  |
| `temperatura_media_c` | double | sí |  |
| `temperatura_max_c` | double | sí |  |
| `temperatura_min_c` | double | sí |  |
| `humedad_relativa_pct` | double | sí |  |
| `brillo_solar_horas_dia` | double | sí |  |
| `fase_enso` | varchar(20) | sí |  |
| `indice_spi` | double | sí |  |
| `es_anio_nino` | bool | sí |  |

### `v_precio_actual`

Último precio por mercado × producto con variación diaria y de 7 días (la usa la pestaña Precios).

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id_central` | int | sí |  |
| `mercado` | varchar(150) | sí |  |
| `ciudad` | varchar(100) | sí |  |
| `id_municipio` | char(5) | sí |  |
| `id_departamento` | char(2) | sí |  |
| `departamento` | varchar(100) | sí |  |
| `id_producto` | int | sí |  |
| `producto` | varchar(100) | sí |  |
| `grupo` | varchar(60) | sí |  |
| `fecha` | date | sí |  |
| `precio_prom_kg` | double | sí |  |
| `precio_min_kg` | double | sí |  |
| `precio_max_kg` | double | sí |  |
| `precio_anterior` | double | sí |  |
| `fecha_anterior` | date | sí |  |
| `var_dia_pct` | double | sí |  |
| `precio_7d` | double | sí |  |
| `var_7d_pct` | double | sí |  |
| `dias_atraso` | int | sí |  |

### `v_predicciones_modelo`

Vista para Power BI: predicciones frente a rendimiento real y metadatos del modelo.

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `codigo_divipola` | char(5) | sí |  |
| `nombre_municipio` | varchar(100) | sí |  |
| `nombre_departamento` | varchar(100) | sí |  |
| `nombre_region` | varchar(50) | sí |  |
| `latitud_centroide` | double | sí |  |
| `longitud_centroide` | double | sí |  |
| `nombre_cultivo` | varchar(100) | sí |  |
| `anio` | smallint | sí |  |
| `rendimiento_real` | double | sí |  |
| `rendimiento_predicho` | double | sí |  |
| `error_absoluto` | double | sí |  |
| `intervalo_confianza_inferior` | double | sí |  |
| `intervalo_confianza_superior` | double | sí |  |
| `nombre_modelo` | varchar(100) | sí |  |
| `metricas_json` | jsonb | sí |  |
| `fecha_entrenamiento` | timestamptz | sí |  |
