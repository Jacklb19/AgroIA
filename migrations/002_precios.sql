-- 002 · Precios mayoristas diarios (SIPSA - DANE): tablas y bitacora de ingesta. La vista v_precio_actual vive en views/.


-- ── CAPA 5: PRECIOS MAYORISTAS DIARIOS (SIPSA - DANE) ─────────────
-- Grano diario por mercado x producto. No usa dim_tiempo (grano mensual).

-- dim_central_abastos ya existe (mercado). Se le agrega el departamento para
-- poder filtrar aunque dim_municipio no tenga cargado el municipio.
ALTER TABLE dim_central_abastos ADD COLUMN IF NOT EXISTS id_departamento CHAR(2);
ALTER TABLE dim_central_abastos ADD COLUMN IF NOT EXISTS nombre_departamento VARCHAR(100);

CREATE TABLE IF NOT EXISTS dim_producto_precio (
    id_producto        SERIAL PRIMARY KEY,
    nombre             VARCHAR(100) NOT NULL,
    nombre_normalizado VARCHAR(100) NOT NULL UNIQUE,
    grupo              VARCHAR(60),
    id_cultivo         INT REFERENCES dim_cultivo(id_cultivo)
);

CREATE TABLE IF NOT EXISTS fact_precio_diario (
    id             BIGSERIAL PRIMARY KEY,
    id_central     INT  NOT NULL REFERENCES dim_central_abastos(id_central),
    id_producto    INT  NOT NULL REFERENCES dim_producto_precio(id_producto),
    fecha          DATE NOT NULL,
    precio_min_kg  DOUBLE PRECISION,
    precio_max_kg  DOUBLE PRECISION,
    precio_prom_kg DOUBLE PRECISION NOT NULL CHECK (precio_prom_kg > 0),
    fuente         VARCHAR(10) NOT NULL DEFAULT 'soap' CHECK (fuente IN ('soap','excel')),
    ingested_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (id_central, id_producto, fecha)
);

CREATE INDEX IF NOT EXISTS idx_fpd_fecha ON fact_precio_diario (fecha DESC);
CREATE INDEX IF NOT EXISTS idx_fpd_serie ON fact_precio_diario (id_producto, id_central, fecha DESC);

CREATE TABLE IF NOT EXISTS pred_precio (
    id             BIGSERIAL PRIMARY KEY,
    id_central     INT  NOT NULL REFERENCES dim_central_abastos(id_central),
    id_producto    INT  NOT NULL REFERENCES dim_producto_precio(id_producto),
    fecha_objetivo DATE NOT NULL,
    horizonte_dias SMALLINT NOT NULL,
    precio_pred_kg DOUBLE PRECISION NOT NULL,
    p10_kg         DOUBLE PRECISION,
    p90_kg         DOUBLE PRECISION,
    metodo         VARCHAR(30) NOT NULL,
    confianza      VARCHAR(10) NOT NULL DEFAULT 'media' CHECK (confianza IN ('alta','media','baja')),
    id_version     INT REFERENCES model_version(id_version),
    generado_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (id_central, id_producto, fecha_objetivo)
);

CREATE TABLE IF NOT EXISTS informe_precio_diario (
    fecha       DATE PRIMARY KEY,
    payload     JSONB NOT NULL,
    generado_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ingest_run (
    id                   SERIAL PRIMARY KEY,
    fuente               VARCHAR(30) NOT NULL,
    started_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at          TIMESTAMPTZ,
    status               VARCHAR(20) NOT NULL DEFAULT 'running'
                         CHECK (status IN ('running','ok','sin_cambios','error')),
    filas_nuevas         INT,
    fecha_dato_max       DATE,
    source_last_modified TIMESTAMPTZ,
    source_ref           VARCHAR(200),
    error                TEXT
);

CREATE INDEX IF NOT EXISTS idx_ingest_run_fuente ON ingest_run (fuente, started_at DESC);

