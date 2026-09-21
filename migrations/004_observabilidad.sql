-- 004 · Observabilidad: resultados de calidad y reportes de extraccion en la BD (antes solo en disco,
-- por eso /api/calidad no funcionaba en Vercel).
CREATE TABLE IF NOT EXISTS quality_check_run (
    id           BIGSERIAL PRIMARY KEY,
    ejecutado_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    indicador    VARCHAR(80) NOT NULL,
    descripcion  TEXT,
    valor        DOUBLE PRECISION,
    estado       VARCHAR(12) NOT NULL CHECK (estado IN ('OK','ALERTA','SIN_DATOS'))
);

CREATE INDEX IF NOT EXISTS idx_quality_check_run ON quality_check_run (indicador, ejecutado_at DESC);

CREATE TABLE IF NOT EXISTS extraction_report (
    fuente          VARCHAR(100) PRIMARY KEY,
    uri             TEXT,
    filas           INT,
    columnas        INT,
    duplicados      INT,
    completitud_pct JSONB,
    extraido_at     TIMESTAMPTZ,
    sincronizado_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
