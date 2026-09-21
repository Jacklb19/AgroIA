"""
extract_sipra.py — Aptitud de suelo por municipio y cultivo (UPRA · SIPRA).

ESTADO DE LA FUENTE (verificado 2026-09-20): el servicio ArcGIS que usaba este extractor
(geoservicios.upra.gov.co/arcgis/rest/services/aptitud_uso_suelo) ya no publica servicios
(la carpeta está vacía y las capas responden "Service ... not started") y el GeoServer de SIPRA
devuelve la página web en lugar de WFS. Mientras UPRA no publique un acceso programático nuevo,
este extractor devuelve un DataFrame vacío y lo dice con un ERROR explícito; en el modelo la
aptitud queda como dato faltante (NaN), nunca como un valor inventado.

Se corrigieron además tres defectos del código original:
  - la columna con el cultivo se llamaba `cultivo_origen` y `clean_suelo` buscaba `producto`,
    por lo que el cultivo se perdía y la aptitud nunca se unía al modelo;
  - no paginaba (ArcGIS devuelve como máximo `maxRecordCount` filas por consulta);
  - desactivaba siempre la verificación SSL.
"""
import logging
import os

import pandas as pd
import requests
import urllib3

from config.settings import DATA_RAW

logger = logging.getLogger(__name__)

# Mapeo de cultivos a sus capas en UPRA. Si un cultivo no está aquí, no se trae su aptitud.
UPRA_SERVICES = {
    "ARROZ": "aptitud_arroz_secano",
    "CAFE": "Aptitud_Cafe_Jul2022",
    "CACAO": "aptitud_cacao_diciembre_2019",
    "PAPA": "aptitud_papa_sem_1_Dic2019",
    "MAIZ": "Aptitud_Maiz_Tradicional",
    "PLATANO": "aptitud_platano",
    "AGUACATE": "aptitud_aguacate_hass_Dic2019",
    "YUCA": "aptitud_yuca",
    "CEBOLLA": "aptitud_cebolla_bulbo_sem_1_Dic2019",
    "ALGODON": "aptitud_algodon_sem_1_Jun2020",
    "BANANO": "aptitud_banano",
    "MANGO": "aptitud_mango_diciembre_2019",
    "PINA": "aptitud_pina",
    "CAUCHO": "aptitud_caucho_diciembre_2019",
    "PALMA DE ACEITE": "aptitud_palma_2018",
}

BASE_URL = "https://geoservicios.upra.gov.co/arcgis/rest/services/aptitud_uso_suelo/{layer}/MapServer/0/query"
PAGINA = 1000
TIMEOUT = 60


def _verificar_ssl() -> bool:
    """SSL verificado por defecto. UPRA_VERIFY_SSL=false solo si el certificado del servidor falla."""
    return os.getenv("UPRA_VERIFY_SSL", "true").lower() != "false"


def _get_json(url: str, params: dict) -> dict:
    verify = _verificar_ssl()
    if not verify:
        urllib3.disable_warnings()
    r = requests.get(url, params=params, verify=verify, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def _descargar_capa(cultivo: str, layer: str) -> pd.DataFrame:
    """Descarga todos los registros de una capa, paginando con resultOffset."""
    url = BASE_URL.format(layer=layer)
    filas: list[dict] = []
    offset = 0
    while True:
        data = _get_json(url, {
            "where": "1=1", "outFields": "cod_dane_mpio,aptitud", "returnGeometry": "false",
            "resultOffset": offset, "resultRecordCount": PAGINA, "f": "json",
        })
        if "error" in data:
            raise RuntimeError(data["error"].get("message", str(data["error"])))
        feats = data.get("features", [])
        filas.extend(f["attributes"] for f in feats)
        if not feats or not data.get("exceededTransferLimit", False):
            break
        offset += len(feats)
    df = pd.DataFrame(filas)
    if df.empty:
        return df
    df = df.rename(columns={"cod_dane_mpio": "id_municipio"})
    df["producto"] = cultivo                    # clave que espera clean_suelo (antes: cultivo_origen)
    df["cultivo_origen"] = cultivo
    if "aptitud" in df.columns:
        df["aptitud"] = df["aptitud"].astype(str).str.replace(r"Exclusi.n", "Exclusion", regex=True)
    return df


def extract_sipra() -> pd.DataFrame:
    """Descarga la aptitud por municipio de cada cultivo disponible. Vacío si la fuente no responde."""
    logger.info("Extrayendo datos de SIPRA (UPRA)...")
    dfs, errores = [], {}
    for cultivo, layer in UPRA_SERVICES.items():
        try:
            df = _descargar_capa(cultivo, layer)
            if not df.empty:
                dfs.append(df)
        except Exception as e:
            errores[cultivo] = str(e)[:120]

    if errores:
        logger.error(
            "SIPRA: %s/%s capas no disponibles (p. ej. %s). La fuente de UPRA cambió o está caída; "
            "sin aptitud de suelo el modelo la trata como dato faltante.",
            len(errores), len(UPRA_SERVICES), next(iter(errores.values())),
        )
    if not dfs:
        logger.warning("No se pudo extraer ningún dato de SIPRA.")
        return pd.DataFrame()

    result = pd.concat(dfs, ignore_index=True)
    out = DATA_RAW / "sipra_aptitud_raw.csv"
    result.to_csv(out, index=False)
    logger.info("Extracción SIPRA completada: %s registros de %s cultivos -> %s", len(result), len(dfs), out)
    return result
