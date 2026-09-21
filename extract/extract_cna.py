"""
extract_cna.py — Censo Nacional Agropecuario 2014 (DANE): uso del suelo por municipio.

Fuente: anexos municipales del Boletín 1, "Cuadro 2": área (ha) en pastos, rastrojo, agrícola e
infraestructura agropecuaria en el área rural dispersa censada. Se cargan tal cual.

Antes este extractor fabricaba `area_cultivos_permanentes_ha` = 60 % y `area_cultivos_transitorios_ha`
= 40 % de una columna equivocada. Esas cifras NO existen en la fuente: el Cuadro 2 no separa cultivos
permanentes y transitorios, así que esas dos columnas quedan vacías (NULL) en vez de inventarse.
"""
import logging

import pandas as pd
import urllib3

from config.settings import DATA_RAW

urllib3.disable_warnings()
logger = logging.getLogger(__name__)

URL_USO_SUELO = "https://www.dane.gov.co/files/CensoAgropecuario/entrega-definitiva/Boletin-1-Uso-del-suelo/1-Anexos-municipales.xls"
HOJA = "Cuadro 2"
ANIO_CENSO = 2014
# posición de cada columna en la hoja (verificado sobre el archivo real)
COL_ID_MUNICIPIO, COL_PASTOS, COL_RASTROJO, COL_AGRICOLA, COL_INFRA = 2, 4, 5, 6, 7


def parsear_cuadro_uso_suelo(raw: pd.DataFrame) -> pd.DataFrame:
    """Recibe la hoja completa (header=None) y devuelve una fila por municipio con códigos DIVIPOLA válidos."""
    df = raw[raw[COL_ID_MUNICIPIO].astype(str).str.strip().str.fullmatch(r"\d{5}")].copy()
    out = pd.DataFrame({
        "id_municipio": df[COL_ID_MUNICIPIO].astype(str).str.strip(),
        "anio_censo": ANIO_CENSO,
        "area_pastos_ha": pd.to_numeric(df[COL_PASTOS], errors="coerce"),
        "area_rastrojo_ha": pd.to_numeric(df[COL_RASTROJO], errors="coerce"),
        "area_agricola_ha": pd.to_numeric(df[COL_AGRICOLA], errors="coerce"),
        "area_infraestructura_ha": pd.to_numeric(df[COL_INFRA], errors="coerce"),
    })
    return out.reset_index(drop=True)


def extract_cna() -> pd.DataFrame:
    """Descarga y parsea el Cuadro 2 del CNA 2014. Vacío si la fuente no responde."""
    logger.info("Extrayendo CNA 2014 (DANE, uso del suelo por municipio)...")
    try:
        raw = pd.read_excel(URL_USO_SUELO, sheet_name=HOJA, header=None)
        df = parsear_cuadro_uso_suelo(raw)
        if df.empty:
            logger.error("CNA: la hoja '%s' no contiene municipios con código DIVIPOLA; ¿cambió el formato?", HOJA)
            return pd.DataFrame()
        out = DATA_RAW / "cna_raw_automatizado.csv"
        df.to_csv(out, index=False)
        logger.info("CNA 2014: %s municipios -> %s", len(df), out)
        return df
    except Exception as e:
        logger.error("Error descargando CNA desde DANE: %s", e)
        return pd.DataFrame()
