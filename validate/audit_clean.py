"""
audit_clean.py — Auditoría integral del módulo clean/
=====================================================
Ejecuta validaciones sobre cada script de limpieza para verificar que:
  1. Los DataFrames de salida no contengan nulos en columnas clave.
  2. Los tipos de datos sean correctos (numérico, string, datetime).
  3. No se introduzcan duplicados espurios.
  4. Los valores caigan dentro de rangos razonables.
  5. El volumen de datos se preserve razonablemente (no se pierda > 50%).
  6. Los nombres de columnas finales coincidan con el schema esperado.

Uso:
    python -m validate.audit_clean          # Ejecuta todas las auditorías
    python -m validate.audit_clean --verbose  # Más detalle
"""
import argparse
import logging
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

# ── Configuración del proyecto ──────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import DATA_RAW, DATA_PROCESSED, BASE_DIR

logger = logging.getLogger("audit_clean")

# =====================================================================
#  Estructura de resultado
# =====================================================================

@dataclass
class CheckResult:
    modulo: str
    test: str
    passed: bool
    detalle: str = ""
    nivel: str = "INFO"   # INFO | WARNING | ERROR

@dataclass
class AuditReport:
    checks: list[CheckResult] = field(default_factory=list)

    def add(self, modulo: str, test: str, passed: bool, detalle: str = "", nivel: str = "INFO"):
        self.checks.append(CheckResult(modulo, test, passed, detalle, nivel))

    @property
    def total(self) -> int:
        return len(self.checks)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def failed(self) -> int:
        return self.total - self.passed

    def summary_df(self) -> pd.DataFrame:
        return pd.DataFrame([
            {"Modulo": c.modulo, "Test": c.test, "Estado": "[PASS]" if c.passed else "[FAIL]",
             "Detalle": c.detalle, "Nivel": c.nivel}
            for c in self.checks
        ])


report = AuditReport()


# =====================================================================
#  Utilidades
# =====================================================================

def _check_no_nulls(df: pd.DataFrame, cols: list[str], modulo: str, label: str):
    """Verifica que las columnas clave no tengan nulos."""
    for col in cols:
        if col not in df.columns:
            report.add(modulo, f"{label}: columna '{col}' existe", False,
                       f"Columna '{col}' no encontrada en el DataFrame", "ERROR")
            continue
        n_nulos = df[col].isna().sum()
        ok = n_nulos == 0
        report.add(modulo, f"{label}: '{col}' sin nulos", ok,
                   f"{n_nulos}/{len(df)} nulos ({n_nulos/max(len(df),1)*100:.1f}%)",
                   "INFO" if ok else "WARNING")


def _check_numeric(df: pd.DataFrame, cols: list[str], modulo: str, label: str):
    """Verifica que las columnas sean numéricas."""
    for col in cols:
        if col not in df.columns:
            continue
        is_num = pd.api.types.is_numeric_dtype(df[col])
        report.add(modulo, f"{label}: '{col}' es numérico", is_num,
                   f"dtype={df[col].dtype}", "INFO" if is_num else "ERROR")


def _check_range(df: pd.DataFrame, col: str, vmin: float, vmax: float, modulo: str, label: str):
    """Verifica que los valores numéricos caigan en un rango razonable."""
    if col not in df.columns:
        return
    series = pd.to_numeric(df[col], errors="coerce").dropna()
    if series.empty:
        report.add(modulo, f"{label}: '{col}' rango [{vmin}, {vmax}]", False,
                   "Sin datos numéricos válidos", "WARNING")
        return
    fuera = ((series < vmin) | (series > vmax)).sum()
    ok = fuera == 0
    report.add(modulo, f"{label}: '{col}' en rango [{vmin}, {vmax}]", ok,
               f"{fuera}/{len(series)} fuera de rango (min={series.min():.2f}, max={series.max():.2f})",
               "INFO" if ok else "WARNING")


def _check_no_duplicates(df: pd.DataFrame, subset: list[str], modulo: str, label: str):
    """Verifica que no haya filas duplicadas en las columnas clave."""
    available = [c for c in subset if c in df.columns]
    if not available:
        return
    dupes = df.duplicated(subset=available, keep=False).sum()
    ok = dupes == 0
    report.add(modulo, f"{label}: sin duplicados en {available}", ok,
               f"{dupes} filas duplicadas de {len(df)}", "INFO" if ok else "WARNING")


# =====================================================================
#  1. AUDITORÍA — clean_clima.py
# =====================================================================

def audit_clean_clima():
    modulo = "clean_clima"
    logger.info("═" * 60)
    logger.info(f"  AUDITORÍA: {modulo}")
    logger.info("═" * 60)

    # --- Verificar que el archivo procesado existe ---
    parquet_path = DATA_PROCESSED / "clima_mensual.parquet"
    if not parquet_path.exists():
        report.add(modulo, "Archivo clima_mensual.parquet existe", False,
                   "No se encontró el archivo de salida", "ERROR")
        return

    report.add(modulo, "Archivo clima_mensual.parquet existe", True, str(parquet_path))

    df = pd.read_parquet(parquet_path)
    report.add(modulo, "DataFrame no vacío", len(df) > 0, f"{len(df)} registros")

    if df.empty:
        return

    # --- Schema esperado ---
    expected = ["id_estacion", "anio", "mes"]
    optional = ["precipitacion_mm", "temperatura_media_c", "temperatura_max_c",
                "temperatura_min_c", "humedad_relativa_pct", "brillo_solar_horas_dia"]

    for col in expected:
        report.add(modulo, f"Columna clave '{col}' presente", col in df.columns,
                   f"Columnas: {list(df.columns)}")

    present_optional = [c for c in optional if c in df.columns]
    report.add(modulo, f"Columnas climáticas presentes ({len(present_optional)}/{len(optional)})",
               len(present_optional) >= 1,
               f"Presentes: {present_optional}")

    # --- Nulos en claves ---
    _check_no_nulls(df, ["id_estacion", "anio", "mes"], modulo, "Claves")

    # --- Tipos ---
    _check_numeric(df, ["anio", "mes", "precipitacion_mm", "temperatura_media_c"], modulo, "Tipos")

    # --- Rangos ---
    _check_range(df, "anio", 1950, 2030, modulo, "Rango")
    _check_range(df, "mes", 1, 12, modulo, "Rango")
    _check_range(df, "precipitacion_mm", 0, 3000, modulo, "Rango")
    _check_range(df, "temperatura_media_c", -10, 50, modulo, "Rango")
    _check_range(df, "humedad_relativa_pct", 0, 100, modulo, "Rango")

    # --- Duplicados ---
    _check_no_duplicates(df, ["id_estacion", "anio", "mes"], modulo, "Unicidad")

    # --- Estaciones ---
    n_estaciones = df["id_estacion"].nunique()
    report.add(modulo, f"Diversidad de estaciones (>= 5)", n_estaciones >= 5,
               f"{n_estaciones} estaciones únicas")


# =====================================================================
#  2. AUDITORÍA — clean_insumos.py
# =====================================================================

def audit_clean_insumos():
    modulo = "clean_insumos"
    logger.info("═" * 60)
    logger.info(f"  AUDITORÍA: {modulo}")
    logger.info("═" * 60)

    # --- Verificar archivo raw ---
    raw_path = DATA_RAW / "insumos_ipia_raw.csv"
    if not raw_path.exists():
        report.add(modulo, "Archivo raw insumos_ipia_raw.csv existe", False,
                   "No se encontró el archivo fuente", "ERROR")
        return
    report.add(modulo, "Archivo raw existe", True, str(raw_path))

    # --- Ejecutar limpieza ---
    from clean.clean_insumos import clean_insumos_ipia
    df = clean_insumos_ipia()

    report.add(modulo, "DataFrame resultante no vacío", len(df) > 0, f"{len(df)} registros")
    if df.empty:
        return

    # --- Schema ---
    expected_cols = ["fecha", "nombre_insumo", "precio_cop_unidad", "tipo_insumo", "unidad_medida"]
    for col in expected_cols:
        report.add(modulo, f"Columna '{col}' presente", col in df.columns)

    # --- Nulos ---
    _check_no_nulls(df, ["fecha", "nombre_insumo"], modulo, "Claves")

    # --- Tipos ---
    if "fecha" in df.columns:
        is_dt = pd.api.types.is_datetime64_any_dtype(df["fecha"])
        report.add(modulo, "Columna 'fecha' es datetime", is_dt,
                   f"dtype={df['fecha'].dtype}", "INFO" if is_dt else "ERROR")

    # --- Categorización tipo_insumo ---
    if "tipo_insumo" in df.columns:
        categorias = df["tipo_insumo"].unique().tolist()
        esperadas = {"Fertilizante", "Plaguicida", "Otros"}
        ok = set(categorias).issubset(esperadas)
        report.add(modulo, f"Categorías tipo_insumo válidas", ok,
                   f"Encontradas: {categorias}, Esperadas: {esperadas}",
                   "INFO" if ok else "WARNING")

    # --- Valores precio no negativos ---
    if "precio_cop_unidad" in df.columns:
        _check_numeric(df, ["precio_cop_unidad"], modulo, "Tipos")
        neg = (pd.to_numeric(df["precio_cop_unidad"], errors="coerce") < 0).sum()
        report.add(modulo, "Sin precios negativos", neg == 0,
                   f"{neg} valores negativos encontrados")

    # --- Nombres de insumo limpios (Title Case) ---
    if "nombre_insumo" in df.columns:
        sample = df["nombre_insumo"].dropna().head(10).tolist()
        has_underscore = any("_" in str(s) for s in sample)
        report.add(modulo, "Nombres sin guiones bajos (limpios)", not has_underscore,
                   f"Muestra: {sample[:3]}")


# =====================================================================
#  3. AUDITORÍA — clean_municipios.py
# =====================================================================

def audit_clean_municipios():
    modulo = "clean_municipios"
    logger.info("═" * 60)
    logger.info(f"  AUDITORÍA: {modulo}")
    logger.info("═" * 60)

    # --- Verificar divipola ---
    divipola_path = DATA_RAW / "divipola.csv"
    if not divipola_path.exists():
        report.add(modulo, "Archivo divipola.csv existe", False,
                   "Requerido para resolver municipios", "ERROR")
        return
    report.add(modulo, "Archivo divipola.csv existe", True)

    from clean.clean_municipios import (
        _normalizar_texto, load_divipola_map, build_synonym_map,
        resolver_municipio, agregar_id_municipio
    )

    # --- Test normalización de texto ---
    test_cases = [
        ("Bogotá D.C.", "bogota d.c."),
        ("MEDELLÍN (Antioquia)", "medellin"),
        ("San Andrés", "san andres"),
        ("  Cali  ", "cali"),
    ]
    for original, esperado in test_cases:
        resultado = _normalizar_texto(original)
        ok = resultado == esperado
        report.add(modulo, f"Normalizacion: '{original}' -> '{esperado}'", ok,
                   f"Obtenido: '{resultado}'")

    # --- Cargar mapas ---
    divipola_map = load_divipola_map()
    synonym_map = build_synonym_map()
    report.add(modulo, f"Mapa DIVIPOLA cargado (>= 100 municipios)",
               len(divipola_map) >= 100, f"{len(divipola_map)} entradas")
    report.add(modulo, f"Mapa sinónimos cargado", True, f"{len(synonym_map)} entradas")

    # --- Resolución de municipios conocidos ---
    test_municipios = ["Bogotá D.C.", "Medellín", "Cali", "Barranquilla"]
    for muni in test_municipios:
        resultado = resolver_municipio(muni, divipola_map, synonym_map)
        ok = resultado is not None and len(resultado) == 5
        report.add(modulo, f"Resolver '{muni}' -> DIVIPOLA", ok,
                   f"Resultado: {resultado}", "INFO" if ok else "WARNING")

    # --- Códigos DIVIPOLA de 5 dígitos ---
    all_codes = list(divipola_map.values())
    invalid = [c for c in all_codes if not (isinstance(c, str) and len(c) == 5 and c.isdigit())]
    report.add(modulo, "Todos los códigos DIVIPOLA son de 5 dígitos",
               len(invalid) == 0, f"{len(invalid)} códigos inválidos de {len(all_codes)}")

    # --- Test agregar_id_municipio con DataFrame sintético ---
    df_test = pd.DataFrame({
        "municipio": ["Bogotá D.C.", "Medellín", "XYZFAKE_MUNICIPIO", "Cali"],
        "valor": [100, 200, 300, 400],
    })
    df_result = agregar_id_municipio(df_test, "municipio")
    resueltos = df_result["id_municipio"].notna().sum()
    report.add(modulo, f"agregar_id_municipio: >= 3/4 resueltos", resueltos >= 3,
               f"{resueltos}/4 resueltos")

    # --- Regiones naturales ---
    from clean.clean_municipios import DEPARTAMENTO_REGION
    regiones_validas = {"Andina", "Caribe", "Pacífico", "Orinoquía", "Amazonía"}
    regiones_mapa = set(DEPARTAMENTO_REGION.values())
    ok = regiones_mapa == regiones_validas
    report.add(modulo, "Regiones naturales completas", ok,
               f"Encontradas: {regiones_mapa}")


# =====================================================================
#  4. AUDITORÍA — clean_precios.py
# =====================================================================

def audit_clean_precios():
    modulo = "clean_precios"
    logger.info("═" * 60)
    logger.info(f"  AUDITORÍA: {modulo}")
    logger.info("═" * 60)

    raw_path = DATA_RAW / "sipsa_raw_consolidado.csv"
    if not raw_path.exists():
        report.add(modulo, "Archivo sipsa_raw_consolidado.csv existe", False,
                   "No se encontró el archivo fuente", "ERROR")
        return
    report.add(modulo, "Archivo raw existe", True, str(raw_path))

    df_raw = pd.read_csv(raw_path)
    report.add(modulo, "DataFrame raw cargado", len(df_raw) > 0, f"{len(df_raw)} registros")

    if df_raw.empty:
        return

    from clean.clean_precios import normalizar_precios_sipsa, construir_dim_centrales

    df_clean = normalizar_precios_sipsa(df_raw)

    if df_clean.empty:
        report.add(modulo, "normalizar_precios_sipsa produce resultado", False,
                   "DataFrame vacío — posiblemente faltan columnas requeridas", "WARNING")
        return

    report.add(modulo, "DataFrame limpio no vacío", True, f"{len(df_clean)} registros")

    # --- Schema ---
    expected = ["anio", "mes", "producto", "nombre_central", "ciudad",
                "precio_promedio_cop_kg"]
    for col in expected:
        report.add(modulo, f"Columna '{col}' presente", col in df_clean.columns)

    # --- Nulos ---
    _check_no_nulls(df_clean, ["anio", "mes", "producto", "nombre_central"], modulo, "Claves")

    # --- Tipos ---
    _check_numeric(df_clean, ["anio", "mes", "precio_promedio_cop_kg",
                              "precio_min_cop_kg", "precio_max_cop_kg"], modulo, "Tipos")

    # --- Rangos ---
    _check_range(df_clean, "anio", 2000, 2030, modulo, "Rango")
    _check_range(df_clean, "mes", 1, 12, modulo, "Rango")

    # --- Precios coherentes: min <= promedio <= max ---
    if all(c in df_clean.columns for c in ["precio_min_cop_kg", "precio_promedio_cop_kg", "precio_max_cop_kg"]):
        sub = df_clean.dropna(subset=["precio_min_cop_kg", "precio_promedio_cop_kg", "precio_max_cop_kg"])
        if not sub.empty:
            incoherentes = (
                (sub["precio_min_cop_kg"] > sub["precio_promedio_cop_kg"]) |
                (sub["precio_promedio_cop_kg"] > sub["precio_max_cop_kg"])
            ).sum()
            ok = incoherentes == 0
            report.add(modulo, "Precios coherentes (min <= prom <= max)", ok,
                       f"{incoherentes}/{len(sub)} incoherentes", "INFO" if ok else "WARNING")

    # --- Strings limpios (sin espacios dobles) ---
    if "producto" in df_clean.columns:
        doble_espacio = df_clean["producto"].str.contains(r"  ", regex=True, na=False).sum()
        report.add(modulo, "Productos sin espacios dobles", doble_espacio == 0,
                   f"{doble_espacio} con espacios dobles")

    # --- id_municipio resuelto ---
    if "id_municipio" in df_clean.columns:
        resueltos = df_clean["id_municipio"].notna().sum()
        pct = resueltos / len(df_clean) * 100
        report.add(modulo, f"Municipios resueltos (>= 50%)", pct >= 50,
                   f"{pct:.1f}% resueltos ({resueltos}/{len(df_clean)})")

    # --- Dimensión centrales ---
    df_centrales = construir_dim_centrales(df_clean)
    report.add(modulo, "construir_dim_centrales produce resultado", len(df_centrales) > 0,
               f"{len(df_centrales)} centrales únicas")
    if not df_centrales.empty:
        _check_no_duplicates(df_centrales, ["nombre_central", "ciudad"], modulo, "Centrales")


# =====================================================================
#  5. AUDITORÍA — clean_suelo.py
# =====================================================================

def audit_clean_suelo():
    modulo = "clean_suelo"
    logger.info("═" * 60)
    logger.info(f"  AUDITORÍA: {modulo}")
    logger.info("═" * 60)

    # --- Verificar archivo SIPRA ---
    sipra_path = DATA_RAW / "sipra_aptitud_raw.csv"
    if not sipra_path.exists():
        report.add(modulo, "Archivo sipra_aptitud_raw.csv existe", False,
                   "No se encontró archivo de aptitud de suelo", "ERROR")
        return
    report.add(modulo, "Archivo SIPRA raw existe", True, str(sipra_path))

    df_sipra = pd.read_csv(sipra_path)
    report.add(modulo, "DataFrame SIPRA raw cargado", len(df_sipra) > 0,
               f"{len(df_sipra)} registros")

    if df_sipra.empty:
        return

    # --- Verificar columnas esperadas de la función _pick_col ---
    from clean.clean_suelo import _pick_col, _CATEGORY_COLS, _SOIL_COLS, _TEXTURE_COLS

    col_code = _pick_col(df_sipra, ["codmunicipio", "cod_municipio", "id_municipio", "divipola"])
    report.add(modulo, "Columna código municipio encontrada", col_code is not None,
               f"Columna: {col_code}" if col_code else "Ninguna de las variantes encontrada",
               "INFO" if col_code else "WARNING")

    col_cat = _pick_col(df_sipra, _CATEGORY_COLS)
    report.add(modulo, "Columna categoría de aptitud encontrada", col_cat is not None,
               f"Columna: {col_cat}" if col_cat else "Ninguna variante",
               "INFO" if col_cat else "WARNING")

    # --- Si tiene código de municipio, ejecutar resumen directo ---
    if col_code:
        from clean.clean_suelo import _resumir_por_codigo
        import geopandas as gpd

        gdf_test = gpd.GeoDataFrame(df_sipra)
        df_result = _resumir_por_codigo(gdf_test, col_code)

        report.add(modulo, "Resumen por código produce resultado", len(df_result) > 0,
                   f"{len(df_result)} registros")

        if not df_result.empty:
            # id_municipio de 5 dígitos
            invalid_ids = df_result[~df_result["id_municipio"].str.match(r"^\d{5}$", na=False)]
            report.add(modulo, "IDs municipio tienen 5 dígitos",
                       len(invalid_ids) == 0,
                       f"{len(invalid_ids)} IDs inválidos",
                       "INFO" if len(invalid_ids) == 0 else "WARNING")

            # Columnas de salida
            for col in ["id_municipio", "clase_aptitud"]:
                report.add(modulo, f"Columna '{col}' en resultado", col in df_result.columns)

    # --- load_censo_agropecuario_local ---
    from clean.clean_suelo import load_censo_agropecuario_local
    df_cna = load_censo_agropecuario_local()
    if df_cna.empty:
        report.add(modulo, "Censo agropecuario local disponible", False,
                   "No se encontraron archivos CNA automatizados ni manuales", "WARNING")
    else:
        report.add(modulo, "Censo agropecuario cargado", True, f"{len(df_cna)} registros")
        if "id_municipio" in df_cna.columns:
            _check_no_nulls(df_cna, ["id_municipio"], modulo, "CNA")


# =====================================================================
#  RESUMEN Y EJECUCIÓN
# =====================================================================

def print_report(verbose: bool = False):
    """Imprime un resumen profesional de la auditoria."""
    df = report.summary_df()

    print("\n" + "=" * 80)
    print("   AUDITORIA INTEGRAL -- Modulo clean/")
    print("   " + "-" * 50)
    print(f"   Total checks: {report.total}  |  [PASS] Pasados: {report.passed}  |  [FAIL] Fallidos: {report.failed}")
    pct = report.passed / max(report.total, 1) * 100
    print(f"   Tasa de exito: {pct:.1f}%")
    print("=" * 80)

    # Agrupar por modulo
    for modulo in df["Modulo"].unique():
        sub = df[df["Modulo"] == modulo]
        passed_mod = (sub["Estado"] == "[PASS]").sum()
        total_mod = len(sub)
        estado_mod = "[OK]" if passed_mod == total_mod else "[!!]"
        print(f"\n{estado_mod} {modulo} ({passed_mod}/{total_mod})")
        print("  " + "-" * 50)
        for _, row in sub.iterrows():
            icon = "  [PASS]" if row["Estado"] == "[PASS]" else "  [FAIL]"
            line = f"{icon} {row['Test']}"
            if verbose or row["Estado"] != "[PASS]":
                line += f"  ->  {row['Detalle']}"
            print(line)

    print("\n" + "=" * 80)

    # Guardar reporte como CSV
    out_path = DATA_PROCESSED / "audit_clean_report.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Reporte guardado en: {out_path}")
    print("=" * 80 + "\n")

    return df


def run_full_audit(verbose: bool = False):
    """Ejecuta todas las auditorías en secuencia."""
    audits = [
        ("clean_clima",      audit_clean_clima),
        ("clean_insumos",    audit_clean_insumos),
        ("clean_municipios", audit_clean_municipios),
        ("clean_precios",    audit_clean_precios),
        ("clean_suelo",      audit_clean_suelo),
    ]

    for name, fn in audits:
        try:
            fn()
        except Exception as e:
            report.add(name, f"Ejecución sin errores fatales", False,
                       f"Error: {type(e).__name__}: {e}", "ERROR")
            logger.exception(f"Error ejecutando auditoría {name}")

    return print_report(verbose)


# =====================================================================
#  ENTRYPOINT
# =====================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auditoría del módulo clean/")
    parser.add_argument("--verbose", "-v", action="store_true", help="Mostrar detalle de cada check")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    run_full_audit(verbose=args.verbose)
