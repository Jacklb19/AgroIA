import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_RAW = BASE_DIR / "data" / "raw"
DATA_PROCESSED = BASE_DIR / "data" / "processed"
LOGS_DIR = BASE_DIR / "logs"
MANUAL_DATA_DIR = DATA_RAW / "manual"

# Crear carpetas si no existen
for d in [DATA_RAW, DATA_PROCESSED, LOGS_DIR, MANUAL_DATA_DIR]:
    d.mkdir(parents=True, exist_ok=True)

class ConfigError(RuntimeError):
    """Falta o es inválida una variable de entorno. El mensaje dice cuál y cómo corregirla."""


def _env(*nombres: str, default: str | None = None) -> str | None:
    """Primer valor no vacío entre los nombres dados (el primero es el nombre oficial, los demás son alias)."""
    for nombre in nombres:
        valor = os.getenv(nombre)
        if valor not in (None, ""):
            return valor
    return default


def _env_int(nombre: str, default: int) -> int:
    valor = os.getenv(nombre)
    if valor in (None, ""):
        return default
    try:
        return int(valor)
    except ValueError:
        raise ConfigError(f"{nombre} debe ser un número entero (valor actual: {valor!r}).") from None


# Conexión a Postgres. Nombre oficial → alias aceptados (para usar el mismo .env que la web):
#   SUPABASE_DB_HOST → DB_HOST · SUPABASE_DB_PORT → DB_PORT · SUPABASE_DB_NAME → DB_NAME
#   SUPABASE_DB_USER → DB_USER · SUPABASE_DB_PASSWORD → DB_PASSWORD, SUPABASE_DB_PASS
DB_LOCALES = ("localhost", "127.0.0.1", "::1")


def db_config(requerido: bool = True) -> dict:
    """
    Parámetros de conexión validados. Con requerido=True falla con un mensaje claro si falta
    algo (antes se construía la URL con "None" y el error salía de psycopg2, ilegible).
    """
    cfg = {
        "host":     _env("SUPABASE_DB_HOST", "DB_HOST"),
        "port":     _env_int("SUPABASE_DB_PORT", _env_int("DB_PORT", 5432)),
        "dbname":   _env("SUPABASE_DB_NAME", "DB_NAME", default="postgres"),
        "user":     _env("SUPABASE_DB_USER", "DB_USER"),
        "password": _env("SUPABASE_DB_PASSWORD", "SUPABASE_DB_PASS", "DB_PASSWORD"),
    }
    if requerido:
        faltan = [
            f"SUPABASE_DB_{k.upper()}" for k in ("host", "user", "password") if not cfg[k]
        ]
        if faltan:
            raise ConfigError(
                "Falta configurar la base de datos: " + ", ".join(faltan)
                + ". Cópialos en .env (ver .env.example); también se aceptan los alias DB_HOST / DB_USER / DB_PASSWORD."
            )
    cfg["local"] = (cfg["host"] or "localhost") in DB_LOCALES
    # DB_SSL: disable | require | verify-full. Por defecto: sin SSL en local, require en remoto.
    ssl = (_env("DB_SSL", default="") or "").lower()
    if ssl and ssl not in ("disable", "require", "verify-full"):
        raise ConfigError(f"DB_SSL debe ser disable, require o verify-full (valor actual: {ssl!r}).")
    cfg["sslmode"] = ssl or ("disable" if cfg["local"] else "require")
    return cfg

# URLs de fuentes
SOURCES = {
    # A04 — datos.gov.co Socrata
    "produccion_datosgov": "https://www.datos.gov.co/resource/uejq-wxrr.json",
    # A06 — SIPSA mayoristas microdatos
    "sipsa_mayoristas": "https://microdatos.dane.gov.co/index.php/catalog/776",
    # A08 — Catálogo estaciones IDEAM Socrata
    "estaciones_ideam": "https://www.datos.gov.co/resource/hp9r-jxuu.json",
    # A09 — Precipitación IDEAM (cada 10 min)
    "precipitacion_ideam": "https://www.datos.gov.co/resource/s54a-sgyg.json",
    # A09b — Datos estaciones IDEAM y terceros (temperatura + variables combinadas)
    "clima_combinado_ideam": "https://www.datos.gov.co/resource/57sv-p2fu.json",
    # A11 — SIPRA GeoJSON (aptitud suelo arroz ejemplo)
    "sipra_geojson": "https://sipra.upra.gov.co/geoserver/ows",
    # DIVIPOLA
    "divipola": "https://www.datos.gov.co/resource/gdxc-w37w.json",
    # ANT — tierras formalizadas (verificar resource ID actual antes de correr)
    "ant_tierras": "https://www.datos.gov.co/resource/ckwx-9gr5.json",
    # Finagro — crédito agropecuario (verificar resource ID actual)
    "finagro_credito": "https://www.datos.gov.co/resource/8e8j-2x86.json",
    # NASA POWER — clima diario reanalysis MERRA-2 (gratis, sin key)
    "nasa_power": "https://power.larc.nasa.gov/api/temporal/daily/point",
    # World Bank Open Data — indicadores macro-agrícolas para Colombia
    "world_bank":  "https://api.worldbank.org/v2/country/COL/indicator",
    # FAOSTAT — producción agrícola oficial FAO/ONU
    "faostat_qcl": "https://fenixservices.fao.org/faostat/api/v1/en/data/QCL",
}

# Token de aplicación de Socrata (opcional): sube el límite de peticiones a datos.gov.co
SOCRATA_TOKEN = os.getenv("SOCRATA_TOKEN") or None

# Radio máximo join espacial clima-municipio (km)
SPATIAL_JOIN_RADIUS_KM = 50

# Período histórico producción
YEAR_START = 2007
YEAR_END   = _env_int("PIPELINE_YEAR_END", datetime.now().year)

# Alertas operativas (opcional): si está definida, un fallo de etapa o datos atrasados se envía a este webhook
# (Slack, Discord y Teams aceptan un POST JSON; ver utils/alertas.py).
ALERT_WEBHOOK_URL = _env("ALERT_WEBHOOK_URL")

# Período histórico clima (más corto para descargas rápidas, ampliar después)
CLIMA_YEAR_START = 2018

# Regiones naturales (orden fijo = id_region)
REGIONES_NATURALES = ["Andina", "Caribe", "Pacífico", "Orinoquía", "Amazonía"]


def _split_env_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


ENSO_BOLETIN_URLS = _split_env_list(os.getenv("ENSO_BOLETIN_URLS"))
