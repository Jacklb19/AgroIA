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

DB = {
    "host":     os.getenv("SUPABASE_DB_HOST"),
    "port":     int(os.getenv("SUPABASE_DB_PORT", 5432)),
    "dbname":   os.getenv("SUPABASE_DB_NAME", "postgres"),
    "user":     os.getenv("SUPABASE_DB_USER", "postgres"),
    "password": os.getenv("SUPABASE_DB_PASSWORD"),
}

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

# Radio máximo join espacial clima-municipio (km)
SPATIAL_JOIN_RADIUS_KM = 50

# Período histórico producción
YEAR_START = 2007
YEAR_END   = int(os.getenv("PIPELINE_YEAR_END", datetime.now().year))

# Período histórico clima (más corto para descargas rápidas, ampliar después)
CLIMA_YEAR_START = 2018

# Regiones naturales (orden fijo = id_region)
REGIONES_NATURALES = ["Andina", "Caribe", "Pacífico", "Orinoquía", "Amazonía"]


def _split_env_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


ENSO_BOLETIN_URLS = _split_env_list(os.getenv("ENSO_BOLETIN_URLS"))
