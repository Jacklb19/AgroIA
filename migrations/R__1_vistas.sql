-- Vistas de consumo (Power BI y web). Repetible: se reaplica cuando este archivo cambia (checksum).
-- Usan CREATE OR REPLACE (sin DROP ... CASCADE): si cambian las columnas de una vista, hace falta una migracion versionada que la elimine antes.


-- Vista 1: Dashboard principal de producción agrícola con clima completo

CREATE OR REPLACE VIEW v_dashboard_agro AS
WITH clima_anual AS (
    SELECT fc.id_municipio,
        tc.anio,
        AVG(fc.precipitacion_mm) AS precipitacion_mm_prom,
        SUM(fc.precipitacion_mm) AS precipitacion_mm_total,
        AVG(fc.temperatura_media_c) AS temperatura_media_c,
        AVG(fc.temperatura_max_c) AS temperatura_max_c,
        AVG(fc.temperatura_min_c) AS temperatura_min_c,
        AVG(fc.humedad_relativa_pct) AS humedad_relativa_pct,
        AVG(fc.brillo_solar_horas_dia) AS brillo_solar_horas_dia
    FROM fact_clima_mensual fc
    JOIN dim_tiempo tc ON tc.id_tiempo = fc.id_tiempo
    GROUP BY fc.id_municipio, tc.anio
)
SELECT m.id_municipio AS codigo_divipola,
    m.nombre_municipio,
    m.nombre_departamento,
    rn.nombre_region,
    m.latitud_centroide,
    m.longitud_centroide,
    c.nombre_cultivo,
    c.tipo_ciclo,
    t.anio,
    fp.area_sembrada_ha,
    fp.area_cosechada_ha,
    fp.produccion_total_ton,
    fp.rendimiento_t_ha,
    ca.precipitacion_mm_prom,
    ca.precipitacion_mm_total,
    ca.temperatura_media_c,
    ca.temperatura_max_c,
    ca.temperatura_min_c,
    ca.humedad_relativa_pct,
    ca.brillo_solar_horas_dia
FROM fact_produccion_agricola fp
JOIN dim_municipio m ON m.id_municipio = fp.id_municipio
JOIN dim_cultivo c ON c.id_cultivo = fp.id_cultivo
JOIN dim_tiempo t ON t.id_tiempo = fp.id_tiempo
LEFT JOIN dim_region_natural rn ON rn.id_region = m.id_region
LEFT JOIN clima_anual ca ON ca.id_municipio = fp.id_municipio AND ca.anio = t.anio;


-- Vista 2: Monitor climático mensual con fase ENSO

CREATE OR REPLACE VIEW v_monitor_climatico AS
SELECT
    m.id_municipio AS codigo_divipola,
    m.nombre_municipio,
    m.nombre_departamento,
    rn.nombre_region,
    m.latitud_centroide,
    m.longitud_centroide,
    e.nombre_estacion,
    t.anio,
    t.mes,
    t.nombre_mes,
    t.trimestre,
    fc.precipitacion_mm,
    fc.temperatura_media_c,
    fc.temperatura_max_c,
    fc.temperatura_min_c,
    fc.humedad_relativa_pct,
    fc.brillo_solar_horas_dia,
    fe.fase_enso,
    fe.indice_spi,
    t.es_anio_nino
FROM fact_clima_mensual fc
JOIN dim_estacion_ideam e ON e.id_estacion = fc.id_estacion
JOIN dim_municipio m ON m.id_municipio = fc.id_municipio
JOIN dim_tiempo t ON t.id_tiempo = fc.id_tiempo
LEFT JOIN dim_region_natural rn ON rn.id_region = m.id_region
LEFT JOIN fact_alerta_enso fe ON fe.id_tiempo = fc.id_tiempo AND fe.id_region = m.id_region;


-- Vista 3: Predicciones del modelo IA vs. datos reales

CREATE OR REPLACE VIEW v_predicciones_modelo AS
SELECT
    m.id_municipio AS codigo_divipola,
    m.nombre_municipio,
    m.nombre_departamento,
    rn.nombre_region,
    m.latitud_centroide,
    m.longitud_centroide,
    c.nombre_cultivo,
    t.anio,
    fp.rendimiento_t_ha AS rendimiento_real,
    pr.rendimiento_predicho_t_ha AS rendimiento_predicho,
    ABS(fp.rendimiento_t_ha - pr.rendimiento_predicho_t_ha) AS error_absoluto,
    pr.intervalo_confianza_inferior,
    pr.intervalo_confianza_superior,
    mv.nombre_modelo,
    mv.metricas_json,
    mv.fecha_entrenamiento
FROM pred_rendimiento pr
JOIN dim_municipio m ON m.id_municipio = pr.id_municipio
JOIN dim_cultivo c ON c.id_cultivo = pr.id_cultivo
JOIN dim_tiempo t ON t.id_tiempo = pr.id_tiempo
JOIN model_version mv ON mv.id_version = pr.id_version AND mv.activo = TRUE
LEFT JOIN dim_region_natural rn ON rn.id_region = m.id_region
LEFT JOIN fact_produccion_agricola fp
    ON fp.id_municipio = pr.id_municipio
   AND fp.id_cultivo = pr.id_cultivo
   AND fp.id_tiempo = pr.id_tiempo;


-- Vista 4: Alertas climáticas activas

CREATE OR REPLACE VIEW v_alertas_climaticas AS
SELECT
    m.id_municipio AS codigo_divipola,
    m.nombre_municipio,
    m.nombre_departamento,
    rn.nombre_region,
    m.latitud_centroide,
    m.longitud_centroide,
    t.anio,
    t.mes,
    t.nombre_mes,
    pa.nivel_riesgo,
    pa.tipo_evento,
    pa.score_probabilidad,
    pa.descripcion_generada,
    mv.nombre_modelo
FROM pred_alerta_climatica pa
JOIN dim_municipio m ON m.id_municipio = pa.id_municipio
JOIN dim_tiempo t ON t.id_tiempo = pa.id_tiempo
LEFT JOIN model_version mv ON mv.id_version = pa.id_version
LEFT JOIN dim_region_natural rn ON rn.id_region = m.id_region
WHERE pa.activa = TRUE;



CREATE OR REPLACE VIEW v_precio_actual AS
WITH ult AS (
    SELECT DISTINCT ON (id_central, id_producto)
           id_central, id_producto, fecha, precio_min_kg, precio_max_kg, precio_prom_kg
    FROM fact_precio_diario
    ORDER BY id_central, id_producto, fecha DESC
),
comp AS (
    SELECT u.*,
        (SELECT f.precio_prom_kg FROM fact_precio_diario f
          WHERE f.id_central = u.id_central AND f.id_producto = u.id_producto AND f.fecha < u.fecha
          ORDER BY f.fecha DESC LIMIT 1) AS precio_anterior,
        (SELECT f.fecha FROM fact_precio_diario f
          WHERE f.id_central = u.id_central AND f.id_producto = u.id_producto AND f.fecha < u.fecha
          ORDER BY f.fecha DESC LIMIT 1) AS fecha_anterior,
        (SELECT f.precio_prom_kg FROM fact_precio_diario f
          WHERE f.id_central = u.id_central AND f.id_producto = u.id_producto AND f.fecha <= u.fecha - 7
          ORDER BY f.fecha DESC LIMIT 1) AS precio_7d
    FROM ult u
)
SELECT c.id_central,
       ca.nombre_central                  AS mercado,
       ca.ciudad,
       ca.id_municipio,
       ca.id_departamento,
       ca.nombre_departamento             AS departamento,
       c.id_producto,
       p.nombre                           AS producto,
       p.grupo,
       c.fecha,
       c.precio_prom_kg,
       c.precio_min_kg,
       c.precio_max_kg,
       c.precio_anterior,
       c.fecha_anterior,
       CASE WHEN c.precio_anterior > 0
            THEN (c.precio_prom_kg - c.precio_anterior) / c.precio_anterior * 100 END AS var_dia_pct,
       c.precio_7d,
       CASE WHEN c.precio_7d > 0
            THEN (c.precio_prom_kg - c.precio_7d) / c.precio_7d * 100 END AS var_7d_pct,
       (CURRENT_DATE - c.fecha)           AS dias_atraso
FROM comp c
JOIN dim_central_abastos ca ON ca.id_central = c.id_central
JOIN dim_producto_precio p  ON p.id_producto = c.id_producto;
