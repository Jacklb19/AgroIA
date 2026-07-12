import pandas as pd
import logging
from pathlib import Path
from config.settings import DATA_RAW, DATA_PROCESSED

logger = logging.getLogger(__name__)

def clean_insumos_ipia() -> pd.DataFrame:
    """Limpia el Índice de Precios de Insumos Agrícolas (IPIA)."""
    raw_path = DATA_RAW / "insumos_ipia_raw.csv"
    if not raw_path.exists():
        logger.warning(f"No existe el archivo raw: {raw_path}")
        return pd.DataFrame()
        
    df = pd.read_csv(raw_path)
    if df.empty:
        return df

    # 1. Convertir fecha
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.normalize()
    
    # 2. Identificar columnas de índices (excluyendo fecha)
    index_cols = [c for c in df.columns if c != "fecha"]
    
    # 3. Transformar a formato largo (Tidy Data)
    # Queremos: fecha, nombre_insumo, precio_cop_unidad
    df_long = df.melt(id_vars=["fecha"], value_vars=index_cols, 
                      var_name="nombre_insumo", value_name="precio_cop_unidad")
    
    # 4. Clasificar tipo_insumo basado en el nombre de la columna original
    def categorizar(nombre):
        nombre = nombre.lower()
        if "fertilizante" in nombre or "urea" in nombre or "dap" in nombre or "kcl" in nombre or "sam" in nombre or "_" in nombre:
            # Los que empiezan con _ suelen ser fertilizantes compuestos como _15_15_15
            if nombre.startswith("_") or any(x in nombre for x in ["fertilizante", "urea", "dap", "kcl", "sam"]):
                return "Fertilizante"
        if "plaguicida" in nombre or "herbicida" in nombre or "fungicida" in nombre or "insecticida" in nombre:
            return "Plaguicida"
        return "Otros"

    df_long["tipo_insumo"] = df_long["nombre_insumo"].apply(categorizar)
    
    # Limpiar nombres para visualización
    df_long["nombre_insumo"] = df_long["nombre_insumo"].str.replace("_", " ").str.strip().str.title()
    
    # Asegurar unidad de medida (IPIA es un índice, base 100, pero lo tratamos como valor)
    df_long["unidad_medida"] = "Indice (Base 100)"
    
    # Guardar procesado
    out_path = DATA_PROCESSED / "insumos_clean.parquet"
    df_long.to_parquet(out_path, index=False)
    logger.info(f"Insumos IPIA limpios: {len(df_long)} registros -> {out_path}")
    
    return df_long

def normalizar_insumos(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Normaliza los datos de insumos (sintéticos o extraídos) para la base de datos."""
    if df_raw.empty:
        return df_raw
    
    df = df_raw.copy()
    
    # 1. Asegurar formato de fecha a datetime si existe
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    else:
        logger.warning("No se encontró columna 'fecha' en insumos.")
        return pd.DataFrame()
        
    # 2. Agregar id_tiempo
    # Obtenemos id_tiempo de la base de datos basándonos en año y mes
    from load.db import get_engine
    engine = get_engine()
    df_tiempo = pd.read_sql("SELECT id_tiempo, anio, mes FROM dim_tiempo", engine)
    
    df["anio"] = df["fecha"].dt.year
    df["mes"] = df["fecha"].dt.month
    
    df = df.merge(df_tiempo, on=["anio", "mes"], how="inner")
    
    # 3. Agregar id_region si existe la columna region
    if "region" in df.columns:
        df_region = pd.read_sql("SELECT id_region, nombre_region FROM dim_region_natural", engine)
        df = df.merge(df_region, left_on="region", right_on="nombre_region", how="left")
    else:
        df["id_region"] = None
        
    # Limpiar
    expected_cols = [
        "id_tiempo",
        "tipo_insumo",
        "nombre_insumo",
        "precio_cop_unidad",
        "unidad_medida",
        "id_region",
        "fuente_origen",
        "es_sintetico",
    ]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = None
            
    df_out = df[expected_cols].dropna(subset=["id_tiempo", "nombre_insumo"])
    
    out_path = DATA_PROCESSED / "insumos_clean.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_parquet(out_path, index=False)
    logger.info(f"Insumos normalizados: {len(df_out)} registros -> {out_path}")
    
    return df_out

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    clean_insumos_ipia()
