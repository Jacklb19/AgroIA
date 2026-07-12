import logging
from pathlib import Path

import pandas as pd

from config.settings import MANUAL_DATA_DIR

logger = logging.getLogger(__name__)


def _parse_spanish_date(date_str: str) -> str:
    """Convierte 'Viernes 24 de abril de 2026' a '2026-04-24'"""
    import re
    meses = {
        "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
        "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
        "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12"
    }
    match = re.search(r'(\d{1,2})\s+de\s+([a-zA-Z]+)\s+de\s+(\d{4})', date_str, re.IGNORECASE)
    if match:
        dia = match.group(1).zfill(2)
        mes = meses.get(match.group(2).lower(), "01")
        anio = match.group(3)
        return f"{anio}-{mes}-{dia}"
    return date_str

def extract_sipsa() -> pd.DataFrame:
    """
    Automatización: Descarga el último anexo de precios diarios mayoristas del SIPSA (DANE)
    y lo transforma de una tabla cruzada a formato tabular plano.
    """
    import requests
    import re
    import urllib3
    urllib3.disable_warnings()

    logger.info("Buscando último boletín SIPSA en DANE...")
    url_base = 'https://www.dane.gov.co/index.php/estadisticas-por-tema/agropecuario/sistema-de-informacion-de-precios-sipsa/componente-precios-mayoristas'
    
    try:
        try:
            r = requests.get(url_base, timeout=30)
            r.raise_for_status()
        except requests.exceptions.SSLError:
            logger.warning("SIPSA: problema de certificado TLS, reintentando con verify=False")
            r = requests.get(url_base, verify=False, timeout=30)
            r.raise_for_status()
        links = re.findall(r'href=[\'"]?([^\'" >]+\.xlsx?)', r.text)
        daily_links = [l for l in list(set(links)) if 'anex-SIPSADiario' in l]
        
        if not daily_links:
            logger.warning("No se encontraron links de SIPSA Diario.")
            return pd.DataFrame()
            
        # Tomar el primero (suele ser el más reciente si ordenamos o asumimos orden de la web)
        # Ordenamos por si acaso, para tomar el más reciente
        daily_links.sort(reverse=True)
        url_file = "https://www.dane.gov.co" + daily_links[0]
        
        logger.info(f"Descargando {url_file}...")
        df_raw = pd.read_excel(url_file, header=None)
        
        fecha_texto = str(df_raw.iloc[1, 0])
        fecha_iso = _parse_spanish_date(fecha_texto)
        
        # Ciudades en fila 2 (índice 2)
        ciudades = {}
        for col in range(1, len(df_raw.columns), 2):
            ciudad = str(df_raw.iloc[2, col]).strip()
            if ciudad != 'nan':
                ciudades[col] = ciudad
                
        records = []
        for idx in range(4, len(df_raw)):
            producto = str(df_raw.iloc[idx, 0]).strip()
            # Ignorar encabezados de categoría o nulos
            if pd.isna(df_raw.iloc[idx, 1]) or producto == 'nan' or 'Fuente:' in producto:
                continue
            
            for col, ciudad in ciudades.items():
                precio = df_raw.iloc[idx, col]
                if pd.notna(precio) and str(precio).strip() != 'n.d.':
                    # Limpiar caracteres especiales de los nombres
                    import unicodedata
                    prod_limpio = unicodedata.normalize("NFKD", producto).encode("ASCII", "ignore").decode("utf-8")
                    ciu_limpia = unicodedata.normalize("NFKD", ciudad).encode("ASCII", "ignore").decode("utf-8")
                    central_limpia = " ".join(ciu_limpia.replace("\r", " ").replace("\n", " ").split())
                    ciudad_base = central_limpia.split(',')[0].strip()
                    
                    records.append({
                        'fecha_registro': fecha_iso,
                        'producto': prod_limpio,
                        'central': central_limpia,
                        'ciudad': ciudad_base,
                        'precio_promedio_cop_kg': precio
                    })
                    
        df_flat = pd.DataFrame(records)
        
        if not df_flat.empty:
            out = MANUAL_DATA_DIR.parent / "sipsa_raw_consolidado.csv"
            df_flat.to_csv(out, index=False)
            logger.info(f"SIPSA automatizado: {len(df_flat)} registros extraídos -> {out}")
            
        return df_flat
        
    except Exception as e:
        logger.error(f"Error automatizando SIPSA: {e}")
        return pd.DataFrame()

