-- ══════════════════════════════════════════════
--  AgroIA Colombia — DDL completo Star Schema
--  Motor: PostgreSQL (Supabase)
-- ══════════════════════════════════════════════

-- ── CAPA 1: DIMENSIONES ────────────────────────

CREATE TABLE IF NOT EXISTS dim_region_natural (
    id_region     SERIAL PRIMARY KEY,
    nombre_region VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dim_municipio (
    id_municipio        CHAR(5) PRIMARY KEY,        -- código DIVIPOLA 5 dígitos
    nombre_municipio    VARCHAR(100) NOT NULL,
    id_departamento     CHAR(2) NOT NULL,
    nombre_departamento VARCHAR(100) NOT NULL,
    id_region           INT REFERENCES dim_region_natural(id_region),
    latitud_centroide   DOUBLE PRECISION,
    longitud_centroide  DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS dim_tiempo (
    id_tiempo   SERIAL PRIMARY KEY,
    fecha       DATE NOT NULL UNIQUE,               -- primer día del mes
    anio        SMALLINT NOT NULL,
    mes         SMALLINT NOT NULL,
    trimestre   SMALLINT NOT NULL,
    semestre    CHAR(1) NOT NULL CHECK (semestre IN ('A','B')),
    nombre_mes  VARCHAR(20) NOT NULL,
    es_anio_nino BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS dim_cultivo (
    id_cultivo        SERIAL PRIMARY KEY,
    nombre_cultivo    VARCHAR(100) NOT NULL,
    nombre_normalizado VARCHAR(100) NOT NULL UNIQUE,
    tipo_ciclo        VARCHAR(20) CHECK (tipo_ciclo IN ('transitorio','permanente')),
    familia_botanica  VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS dim_estacion_ideam (
    id_estacion     VARCHAR(20) PRIMARY KEY,
    nombre_estacion VARCHAR(150),
    tipo_estacion   VARCHAR(50),
    latitud         DOUBLE PRECISION,
    longitud        DOUBLE PRECISION,
    altitud_msnm    DOUBLE PRECISION,
    id_municipio    CHAR(5) REFERENCES dim_municipio(id_municipio),
    estado_activa   BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS dim_central_abastos (
    id_central   SERIAL PRIMARY KEY,
    nombre_central VARCHAR(150) NOT NULL,
    ciudad         VARCHAR(100) NOT NULL,
    id_municipio   CHAR(5) REFERENCES dim_municipio(id_municipio),
    UNIQUE (nombre_central, ciudad)
);

-- ── CAPA 2: HECHOS HISTÓRICOS ─────────────────

CREATE TABLE IF NOT EXISTS fact_produccion_agricola (
    id               SERIAL PRIMARY KEY,
    id_municipio     CHAR(5) NOT NULL REFERENCES dim_municipio(id_municipio),
    id_cultivo       INT     NOT NULL REFERENCES dim_cultivo(id_cultivo),
    id_tiempo        INT     NOT NULL REFERENCES dim_tiempo(id_tiempo),
    area_sembrada_ha       DOUBLE PRECISION,
    area_cosechada_ha      DOUBLE PRECISION,
    produccion_total_ton   DOUBLE PRECISION,
    rendimiento_t_ha       DOUBLE PRECISION,
    fuente_origen          VARCHAR(50),
    UNIQUE (id_municipio, id_cultivo, id_tiempo)
);

CREATE TABLE IF NOT EXISTS fact_clima_mensual (
    id               SERIAL PRIMARY KEY,
    id_estacion      VARCHAR(20) NOT NULL REFERENCES dim_estacion_ideam(id_estacion),
    id_municipio     CHAR(5)     NOT NULL REFERENCES dim_municipio(id_municipio),
    id_tiempo        INT         NOT NULL REFERENCES dim_tiempo(id_tiempo),
    precipitacion_mm           DOUBLE PRECISION,
    temperatura_media_c        DOUBLE PRECISION,
    temperatura_max_c          DOUBLE PRECISION,
    temperatura_min_c          DOUBLE PRECISION,
    humedad_relativa_pct       DOUBLE PRECISION,
    brillo_solar_horas_dia     DOUBLE PRECISION,
    UNIQUE (id_estacion, id_tiempo)
);

CREATE TABLE IF NOT EXISTS fact_precios_mayoristas (
    id               SERIAL PRIMARY KEY,
    id_central       INT  NOT NULL REFERENCES dim_central_abastos(id_central),
    id_cultivo       INT  NOT NULL REFERENCES dim_cultivo(id_cultivo),
    id_tiempo        INT  NOT NULL REFERENCES dim_tiempo(id_tiempo),
    precio_min_cop_kg        DOUBLE PRECISION,
    precio_max_cop_kg        DOUBLE PRECISION,
    precio_promedio_cop_kg   DOUBLE PRECISION,
    volumen_abastecimiento_ton DOUBLE PRECISION,
    UNIQUE (id_central, id_cultivo, id_tiempo)
);

CREATE TABLE IF NOT EXISTS fact_aptitud_suelo (
    id               SERIAL PRIMARY KEY,
    id_municipio     CHAR(5) NOT NULL REFERENCES dim_municipio(id_municipio),
    id_cultivo       INT REFERENCES dim_cultivo(id_cultivo),
    clase_aptitud    VARCHAR(20) CHECK (clase_aptitud IN ('alta','moderada','marginal','no_apta')),
    UNIQUE (id_municipio, id_cultivo)
);

CREATE TABLE IF NOT EXISTS fact_censo_agropecuario (
    id               SERIAL PRIMARY KEY,
    id_municipio     CHAR(5) NOT NULL REFERENCES dim_municipio(id_municipio),
    anio_censo       SMALLINT NOT NULL,
    area_cultivos_permanentes_ha     DOUBLE PRECISION,
    area_cultivos_transitorios_ha    DOUBLE PRECISION,
    UNIQUE (id_municipio, anio_censo)
);

CREATE TABLE IF NOT EXISTS fact_alerta_enso (
    id               SERIAL PRIMARY KEY,
    id_tiempo        INT  NOT NULL REFERENCES dim_tiempo(id_tiempo),
    id_region        INT  NOT NULL REFERENCES dim_region_natural(id_region),
    fase_enso        VARCHAR(20), -- El Niño, La Niña, Neutro
    indice_spi       DOUBLE PRECISION,
    anomalia_precipitacion_pct DOUBLE PRECISION,
    probabilidad_deficit_hidrico DOUBLE PRECISION,
    probabilidad_exceso_hidrico  DOUBLE PRECISION,
    fuente_origen    VARCHAR(100),
    es_sintetico     BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (id_tiempo, id_region)
);

CREATE TABLE IF NOT EXISTS fact_precios_insumos (
    id               SERIAL PRIMARY KEY,
    id_tiempo        INT  NOT NULL REFERENCES dim_tiempo(id_tiempo),
    tipo_insumo      VARCHAR(50),
    nombre_insumo    VARCHAR(100),
    precio_cop_unidad DOUBLE PRECISION,
    unidad_medida    VARCHAR(20),
    id_region        INT REFERENCES dim_region_natural(id_region),
    fuente_origen    VARCHAR(100),
    es_sintetico     BOOLEAN NOT NULL DEFAULT FALSE
);

-- ── CAPA 3: MODELO IA ─────────────────────────

CREATE TABLE IF NOT EXISTS model_version (
    id_version        SERIAL PRIMARY KEY,
    nombre_modelo     VARCHAR(100) NOT NULL,
    fecha_entrenamiento TIMESTAMPTZ DEFAULT NOW(),
    metricas_json     JSONB,
    activo            BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS pred_rendimiento (
    id               SERIAL PRIMARY KEY,
    id_municipio     CHAR(5) NOT NULL REFERENCES dim_municipio(id_municipio),
    id_cultivo       INT     NOT NULL REFERENCES dim_cultivo(id_cultivo),
    id_tiempo        INT     NOT NULL REFERENCES dim_tiempo(id_tiempo),
    rendimiento_predicho_t_ha      DOUBLE PRECISION,
    intervalo_confianza_inferior   DOUBLE PRECISION,
    intervalo_confianza_superior   DOUBLE PRECISION,
    id_version       INT REFERENCES model_version(id_version)
);

CREATE TABLE IF NOT EXISTS pred_alerta_climatica (
    id               SERIAL PRIMARY KEY,
    id_municipio     CHAR(5) NOT NULL REFERENCES dim_municipio(id_municipio),
    id_tiempo        INT     NOT NULL REFERENCES dim_tiempo(id_tiempo),
    nivel_riesgo     VARCHAR(10) CHECK (nivel_riesgo IN ('BAJO','MEDIO','ALTO')),
    tipo_evento      VARCHAR(30),
    score_probabilidad DOUBLE PRECISION,
    descripcion_generada TEXT,
    activa           BOOLEAN DEFAULT TRUE,
    id_version       INT REFERENCES model_version(id_version)
);

ALTER TABLE fact_alerta_enso
    ADD COLUMN IF NOT EXISTS fuente_origen VARCHAR(100);

ALTER TABLE fact_alerta_enso
    ADD COLUMN IF NOT EXISTS es_sintetico BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE fact_precios_insumos
    ADD COLUMN IF NOT EXISTS fuente_origen VARCHAR(100);

ALTER TABLE fact_precios_insumos
    ADD COLUMN IF NOT EXISTS es_sintetico BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE fact_precios_insumos
    DROP CONSTRAINT IF EXISTS fact_precios_insumos_id_tiempo_tipo_insumo_nombre_insumo_key;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fact_precios_insumos_unique_region'
    ) THEN
        ALTER TABLE fact_precios_insumos
            ADD CONSTRAINT fact_precios_insumos_unique_region
            UNIQUE (id_tiempo, tipo_insumo, nombre_insumo, id_region);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'pred_rendimiento_unique_natural_key'
    ) THEN
        ALTER TABLE pred_rendimiento
            ADD CONSTRAINT pred_rendimiento_unique_natural_key
            UNIQUE (id_municipio, id_cultivo, id_tiempo);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'pred_alerta_climatica_unique_natural_key'
    ) THEN
        ALTER TABLE pred_alerta_climatica
            ADD CONSTRAINT pred_alerta_climatica_unique_natural_key
            UNIQUE (id_municipio, id_tiempo);
    END IF;
END $$;

-- ── CAPA 3.5: MEMORIA CONVERSACIONAL DEL ASISTENTE ────────────────
CREATE TABLE IF NOT EXISTS chat_session (
    id_session     UUID PRIMARY KEY,
    user_label     VARCHAR(120),
    creada_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ultima_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_message (
    id             SERIAL PRIMARY KEY,
    id_session     UUID NOT NULL REFERENCES chat_session(id_session) ON DELETE CASCADE,
    role           VARCHAR(15) NOT NULL CHECK (role IN ('user','assistant','tool')),
    content        TEXT,
    metadata       JSONB,
    creada_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_message_session ON chat_message(id_session, creada_at);

-- ── CAPA 4: VISTAS POWER BI ────────────────────

-- Vista 1: Dashboard principal de producción agrícola con clima completo
DROP VIEW IF EXISTS v_dashboard_agro CASCADE;

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
DROP VIEW IF EXISTS v_monitor_climatico CASCADE;

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
DROP VIEW IF EXISTS v_predicciones_modelo CASCADE;

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
DROP VIEW IF EXISTS v_alertas_climaticas CASCADE;

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
