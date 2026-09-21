-- 003 · Contadores diarios del asistente (/api/chat). Antes los creaba web/lib/rateLimit.js en tiempo de ejecucion;
-- ahora vive aqui para que el rol web pueda ser de solo lectura salvo en las tablas chat_*.
CREATE TABLE IF NOT EXISTS chat_rate (
    clave TEXT NOT NULL,
    dia   DATE NOT NULL,
    n     INT  NOT NULL DEFAULT 0,
    PRIMARY KEY (clave, dia)
);
