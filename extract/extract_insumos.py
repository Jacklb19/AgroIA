"""
extract_insumos.py — Fuente A07: Precios de Insumos Agrícolas
Fuente real: DANE SIPSA-I (Sistema de Información de Precios y Abastecimiento
del Sector Agropecuario, Componente de Insumos y Factores Asociados a la
Producción Agropecuaria) — series históricas oficiales, mensuales, por
departamento, enero 2013 - presente.

Prioridad: series históricas DANE (reales) -> archivos manuales -> (opcional,
solo si ALLOW_SYNTHETIC_INSUMOS=true) serie sintética de último recurso.

Nota: los 3 endpoints Socrata usados anteriormente (y5zy-x4ky, 4td6-4v3h,
t4ep-xtez) están dados de baja (HTTP 404 confirmado) — SIPSA-I no se publica
como dataset tabular en datos.gov.co, solo como archivos Excel en dane.gov.co.
"""
import logging
import os
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from config.settings import MANUAL_DATA_DIR
from clean.clean_municipios import DEPARTAMENTO_REGION

logger = logging.getLogger(__name__)

# Series históricas oficiales SIPSA-I (DANE), por departamento.
# El archivo 2013-2020 solo cubre hasta 2017-12 en la práctica (se descartan
# sus filas >= 2018 porque el archivo 2018-2026 las reporta con más detalle).
_DANE_HISTORICO_URLS = [
    "https://www.dane.gov.co/files/operaciones/SIPSA/anex-series-historicas-insumos-2013-2020.xlsx",
    "https://www.dane.gov.co/files/operaciones/SIPSA/anex-SIPSAInsumos-SeriesHistoricasDep-2018-2026.xlsx",
]
_CORTE_ARCHIVO_ANTIGUO = pd.Timestamp("2018-01-01")

_SHEET_RE = re.compile(r"^\d+\.\d+$")

_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

# Mapeo Subgrupo oficial SIPSA-I -> categoría de insumo usada por el modelo.
# Solo se conservan subgrupos agrícolas relevantes para rendimiento de cultivos;
# se descartan subgrupos exclusivamente pecuarios (antibióticos, vitaminas
# animales, medicamentos veterinarios, alimentos balanceados, etc.) que no
# aplican al modelo de rendimiento de cultivos.
_SUBGRUPO_TIPO = {
    "fertilizantes, enmiendas y acondicionadores de suelo": "fertilizante",
    "fungicidas": "agroquimico",
    "herbicidas": "agroquimico",
    "insecticidas, acaricidas y nematicidas": "agroquimico",
    "insecticidas, plaguicidas y repelentes": "agroquimico",
    "coadyuvantes, molusquicidas, reguladores fisiológicos y otros": "agroquimico",
    "material de propagación": "semilla",
    "bioinsumos": "bioinsumo",
    "elementos agropecuarios": "otros",
    "empaques agropecuarios": "otros",
    "servicios agrícolas": "otros",
    "arrendamiento de tierras": "arrendamiento",
    "jornales": "mano_de_obra",
}


def _normaliza(txt) -> str:
    return re.sub(r"\s+", " ", str(txt)).strip().lower()


def _extraer_subgrupo(df_raw: pd.DataFrame) -> str | None:
    """Busca en las primeras filas de la hoja el título tipo '1.2. Fertilizantes...'."""
    for i in range(min(10, len(df_raw))):
        val = df_raw.iloc[i, 0]
        if isinstance(val, str) and re.match(r"^\d+\.\d+\.", val.strip()):
            return re.sub(r"^\d+\.\d+\.\s*", "", val.strip())
    return None


def _extraer_header_row(df_raw: pd.DataFrame) -> int | None:
    """Busca la fila de encabezado real (empieza con 'Año')."""
    for i in range(min(15, len(df_raw))):
        val = df_raw.iloc[i, 0]
        if isinstance(val, str) and val.strip().lower() == "año":
            return i
    return None


def _parse_hoja(xls: pd.ExcelFile, sheet: str) -> pd.DataFrame:
    df_raw = pd.read_excel(xls, sheet_name=sheet, header=None)
    subgrupo = _extraer_subgrupo(df_raw)
    if subgrupo is None or _normaliza(subgrupo) not in _SUBGRUPO_TIPO:
        return pd.DataFrame()

    header_row = _extraer_header_row(df_raw)
    if header_row is None:
        return pd.DataFrame()

    df = pd.read_excel(xls, sheet_name=sheet, header=header_row)
    df.columns = [str(c).strip() for c in df.columns]
    if "Año" not in df.columns:
        return pd.DataFrame()
    df = df.dropna(subset=["Año"])
    if df.empty:
        return pd.DataFrame()

    col_precio = "Precio promedio departamento" if "Precio promedio departamento" in df.columns else "Precio promedio"
    if col_precio not in df.columns or "Código departamento" not in df.columns:
        return pd.DataFrame()

    df = df.rename(columns={
        col_precio: "precio",
        "Código departamento": "cod_departamento",
    })
    df["subgrupo"] = subgrupo
    df["tipo_insumo"] = _SUBGRUPO_TIPO[_normaliza(subgrupo)]
    return df[["Año", "Mes", "cod_departamento", "subgrupo", "tipo_insumo", "precio"]]


def _fetch_dane_historico() -> pd.DataFrame:
    """Descarga y parsea las series históricas reales SIPSA-I (DANE)."""
    frames = []
    for idx, url in enumerate(_DANE_HISTORICO_URLS):
        try:
            logger.info("Descargando series históricas SIPSA-I: %s", url)
            xls = pd.ExcelFile(url)
        except Exception as exc:
            logger.warning("No se pudo descargar %s: %s", url, exc)
            continue

        sheets = [s for s in xls.sheet_names if _SHEET_RE.match(s)]
        for sheet in sheets:
            try:
                df_sheet = _parse_hoja(xls, sheet)
                if not df_sheet.empty:
                    df_sheet["_archivo_idx"] = idx
                    frames.append(df_sheet)
            except Exception as exc:
                logger.debug("Hoja %s de %s no se pudo procesar: %s", sheet, url, exc)

    if not frames:
        logger.warning("Insumos A07: no se pudo leer ninguna hoja de las series históricas DANE.")
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)

    df["mes_num"] = df["Mes"].astype(str).str.strip().str.lower().map(_MESES)
    df["anio"] = pd.to_numeric(df["Año"], errors="coerce")
    df = df.dropna(subset=["mes_num", "anio"])
    df["anio"] = df["anio"].astype(int)
    df["mes_num"] = df["mes_num"].astype(int)
    df["fecha"] = pd.to_datetime(dict(year=df["anio"], month=df["mes_num"], day=1))

    # El archivo antiguo (idx 0) solo aporta el período que el archivo nuevo
    # (idx 1, 2018-2026) no cubre, para evitar promediar dos fuentes redundantes.
    df = df[~((df["_archivo_idx"] == 0) & (df["fecha"] >= _CORTE_ARCHIVO_ANTIGUO))]

    df["cod_departamento"] = (
        df["cod_departamento"].astype(str).str.extract(r"(\d+)")[0].str.zfill(2)
    )
    df["region"] = df["cod_departamento"].map(DEPARTAMENTO_REGION)
    df["precio"] = pd.to_numeric(df["precio"], errors="coerce")
    df = df.dropna(subset=["precio", "region"])
    df = df[df["precio"] > 0]

    if df.empty:
        return pd.DataFrame()

    # Cientos de productos/marcas comerciales específicas (p.ej. "Alisin",
    # "Brocaril Wp") se resumen en su subgrupo oficial SIPSA-I para obtener
    # un precio promedio de mercado por región-mes-categoría, en vez de una
    # serie dispersa por marca que no aporta señal útil al modelo.
    df_agg = (
        df.groupby(["fecha", "region", "tipo_insumo", "subgrupo"], as_index=False)["precio"]
        .mean()
        .rename(columns={"subgrupo": "nombre_insumo", "precio": "precio_cop_unidad"})
    )
    df_agg["unidad_medida"] = "Precio promedio de mercado (COP)"
    df_agg["fuente_origen"] = "DANE SIPSA-I (series históricas reales)"
    df_agg["es_sintetico"] = False

    logger.info(
        "Insumos DANE SIPSA-I: %s registros reales (%s a %s)",
        len(df_agg), df_agg["fecha"].min().date(), df_agg["fecha"].max().date(),
    )
    return df_agg


def _load_manual_files() -> pd.DataFrame:
    base = MANUAL_DATA_DIR / "insumos"
    if not base.exists():
        return pd.DataFrame()
    files: list[Path] = []
    for pattern in ("*.csv", "*.xlsx", "*.xls", "*.parquet"):
        files.extend(sorted(base.glob(pattern)))
    if not files:
        return pd.DataFrame()

    frames = []
    for path in files:
        logger.info("Leyendo archivo de insumos: %s", path.name)
        suffix = path.suffix.lower()
        if suffix == ".csv":
            frames.append(pd.read_csv(path))
        elif suffix == ".parquet":
            frames.append(pd.read_parquet(path))
        else:
            frames.append(pd.read_excel(path))

    result = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not result.empty:
        result["fuente_origen"] = "manual"
        result["es_sintetico"] = False
    logger.info("Insumos manuales: %s registros", len(result))
    return result


def _generate_synthetic_ipia() -> pd.DataFrame:
    """
    Genera serie temporal SINTÉTICA de precios de insumos agrícolas (2020-presente).
    Solo se usa como último recurso si ALLOW_SYNTHETIC_INSUMOS=true en el entorno
    y no hay datos reales disponibles (DANE caído y sin archivos manuales).
    NO representa precios reales de mercado — no usar para análisis o predicciones
    que se presenten como basadas en datos reales.
    """
    dates = pd.date_range("2020-01", f"{datetime.now().year}-12", freq="MS")
    regiones = ["Andina", "Caribe", "Pacífico", "Orinoquía", "Amazonía"]

    insumos = [
        ("fertilizante",  "Fertilizantes, enmiendas y acondicionadores de suelo", 1_300_000, "ton"),
        ("agroquimico",   "Herbicidas",                                             42_000, "litro"),
        ("agroquimico",   "Fungicidas",                                             85_000, "litro"),
        ("mano_de_obra",  "Jornales",                                               40_000, "jornal"),
        ("semilla",       "Material de propagación",                                8_000, "kg"),
    ]

    rng = np.random.default_rng(42)
    rows = []

    for tipo, nombre, precio_base, unidad in insumos:
        for region in regiones:
            precio = float(precio_base)
            for fecha in dates:
                annual_growth = rng.uniform(0.08, 0.16)
                monthly_factor = (1 + annual_growth) ** (1 / 12)
                noise = rng.normal(1.0, 0.015)
                precio = precio * monthly_factor * noise
                rows.append({
                    "fecha":             fecha,
                    "tipo_insumo":       tipo,
                    "nombre_insumo":     nombre,
                    "precio_cop_unidad": round(precio, 2),
                    "unidad_medida":     unidad,
                    "region":            region,
                })

    df = pd.DataFrame(rows)
    df["fuente_origen"] = "IPIA sintetico"
    df["es_sintetico"] = True
    logger.warning(
        "Insumos A07: %s registros SINTÉTICOS generados (ALLOW_SYNTHETIC_INSUMOS=true). "
        "Esto NO son precios reales.", len(df),
    )
    return df


def extract_insumos() -> pd.DataFrame:
    """
    Extrae precios de insumos agrícolas A07.
    Prioridad: series históricas reales DANE SIPSA-I -> archivos en
    data/raw/manual/insumos/ -> (solo si ALLOW_SYNTHETIC_INSUMOS=true) serie sintética.
    """
    df = _fetch_dane_historico()
    if df.empty:
        df = _load_manual_files()
    if df.empty:
        if os.getenv("ALLOW_SYNTHETIC_INSUMOS", "false").lower() == "true":
            df = _generate_synthetic_ipia()
        else:
            logger.error(
                "Insumos A07: no fue posible obtener datos REALES (DANE SIPSA-I no disponible "
                "y no hay archivos manuales en data/raw/manual/insumos/). Se omite la carga de "
                "fact_precios_insumos en esta corrida en vez de insertar datos sintéticos. "
                "Para forzar datos sintéticos de emergencia, define ALLOW_SYNTHETIC_INSUMOS=true."
            )
            return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    out = MANUAL_DATA_DIR.parent / "insumos_raw_consolidado.parquet"
    df.to_parquet(out, index=False)
    logger.info("Insumos raw -> %s (%s registros)", out, len(df))
    return df
