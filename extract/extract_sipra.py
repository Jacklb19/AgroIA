import logging
import requests
import pandas as pd
import urllib3

urllib3.disable_warnings()

from config.settings import DATA_RAW

logger = logging.getLogger(__name__)

# Mapeo de algunos cultivos comunes a sus servicios en UPRA
# Si un cultivo de nuestra base no está aquí, no le traeremos aptitud.
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
    "PALMA DE ACEITE": "aptitud_palma_2018"
}

def extract_sipra() -> pd.DataFrame:
    """
    Descarga la aptitud de suelo por municipio directamente desde la API REST de ArcGIS de la UPRA.
    """
    logger.info("Extrayendo datos de SIPRA (API UPRA)...")
    base_url = "https://geoservicios.upra.gov.co/arcgis/rest/services/aptitud_uso_suelo/{layer}/MapServer/0/query"
    
    dfs = []
    
    for cultivo, layer in UPRA_SERVICES.items():
        logger.info(f"  -> Consultando UPRA: {cultivo}")
        url = base_url.format(layer=layer)
        # Queremos traer el código del municipio y la aptitud
        params = {
            "where": "1=1",
            "outFields": "cod_dane_mpio,aptitud",
            "f": "json",
            "returnGeometry": "false"
        }
        
        try:
            r = requests.get(url, params=params, verify=False, timeout=60)
            r.raise_for_status()
            data = r.json()
            
            if "features" in data:
                records = [f["attributes"] for f in data["features"]]
                df = pd.DataFrame(records)
                if not df.empty:
                    # Renombrar columnas al estándar raw
                    df = df.rename(columns={"cod_dane_mpio": "id_municipio"})
                    df["cultivo_origen"] = cultivo
                    
                    # Limpiar caracteres raros de "Exclusión"
                    if "aptitud" in df.columns:
                        df["aptitud"] = df["aptitud"].astype(str).str.replace(r'Exclusi.n', 'Exclusion', regex=True)
                    
                    dfs.append(df)
            else:
                logger.warning(f"No se encontraron 'features' para {layer}")
        except Exception as e:
            logger.error(f"Error descargando {layer} de UPRA: {e}")
            
    if dfs:
        result = pd.concat(dfs, ignore_index=True)
        out = DATA_RAW / "sipra_aptitud_raw.csv"
        result.to_csv(out, index=False)
        logger.info(f"Extracción SIPRA completada: {len(result)} registros consolidados -> {out}")
        return result
    else:
        logger.warning("No se pudo extraer ningún dato de SIPRA.")
        return pd.DataFrame()
