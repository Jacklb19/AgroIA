"""
run_pipeline.py — Orquestador profesional del ETL AgroIA Colombia
Uso: python run_pipeline.py --mode all --once
"""
import argparse
import logging
import pandas as pd
import numpy as np
from config.settings import LOGS_DIR
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, TextColumn

# Configuración de consola profesional
console = Console(safe_box=True, legacy_windows=False)

# Logging (Silencioso en consola, detallado en archivo)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "etl_run.log", encoding="utf-8"),
        # Eliminamos el StreamHandler de logging para manejarlo con Rich
    ],
)
logger = logging.getLogger("pipeline")

def print_banner():
    console.print(Panel.fit(
        "[bold green]Plataforma AgroIA Colombia[/bold green]\n"
        "[dim]Sistema de Inteligencia para la Resiliencia Agrícola 2026[/dim]",
        border_style="green"
    ))

def run_core_etl(engine=None):
    console.rule("[bold blue]PASO 1: ETL CORE (Producción y Clima)")
    
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        task = progress.add_task("Inicializando componentes...", total=None)
        
        from extract.extract_divipola    import extract_divipola
        from extract.extract_produccion  import extract_produccion
        from clean.clean_municipios      import (
            agregar_id_municipio,
            asignar_estaciones_a_municipios,
            build_region_map_from_divipola,
        )
        from clean.clean_clima           import unificar_clima_mensual
        from clean.clean_produccion      import normalizar_produccion
        from load.load_facts             import _normalizar_nombre
        from load.db                     import get_engine, init_schema
        from load.load_dimensions        import (
            load_dim_region_natural, load_dim_tiempo,
            load_dim_municipio, load_dim_cultivo,
            load_dim_estacion_ideam
        )
        from load.load_facts             import load_all_facts, load_fact_clima_mensual
        from validate.quality_report     import run_quality_report

        if engine is None:
            engine = get_engine()

        # ── 1. Schema ──
        progress.update(task, description="[cyan]Configurando base de datos...")
        init_schema(engine)

        # ── 2. Extracción ──
        progress.update(task, description="[cyan]Extrayendo DIVIPOLA y Producción A04/A05...")
        df_divipola    = extract_divipola()
        df_produccion  = extract_produccion()
        
        # Nombres del esquema (acepta las columnas crudas de Socrata y las ya renombradas por el extractor)
        df_produccion = normalizar_produccion(df_produccion)

        progress.update(task, description="[cyan]Obteniendo catálogo IDEAM...")
        from extract.extract_ideam_estaciones import extract_estaciones
        df_estaciones = extract_estaciones()

        progress.update(task, description="[cyan]Descargando series climáticas (V4)...")
        from extract.extract_ideam_clima import extract_all_clima
        df_precip_mensual, df_combinado_mensual = extract_all_clima()

        # ── 3. Dimensiones ──
        progress.update(task, description="[cyan]Cargando dimensiones maestras...")
        load_dim_region_natural(engine)
        load_dim_tiempo(engine)
        df_region_map = build_region_map_from_divipola(df_divipola)
        load_dim_municipio(engine, df_divipola, df_region_map=df_region_map)
        
        df_cultivos = df_produccion[["cultivo", "grupo_de_cultivo", "ciclo_de_cultivo"]].drop_duplicates()
        df_cultivos = df_cultivos.rename(columns={
            "cultivo": "nombre_cultivo", "grupo_de_cultivo": "familia_botanica", "ciclo_de_cultivo": "tipo_ciclo"
        })
        # Misma normalización (sin tildes) que usa load_all_facts para unir producción con dim_cultivo:
        # con solo upper() los cultivos con tilde (Café, Plátano, Maíz, Caña...) no coincidían y se perdían.
        df_cultivos["nombre_normalizado"] = df_cultivos["nombre_cultivo"].astype(str).map(_normalizar_nombre)
        df_cultivos["tipo_ciclo"] = df_cultivos["tipo_ciclo"].astype(str).str.lower()
        df_cultivos.loc[~df_cultivos["tipo_ciclo"].isin(['transitorio','permanente']), "tipo_ciclo"] = None
        df_cultivos = df_cultivos.replace({np.nan: None, "nan": None, "None": None})
        load_dim_cultivo(engine, df_cultivos)

        # ── 4. Limpieza ──
        progress.update(task, description="[cyan]Ejecutando limpieza espacial...")
        if "id_municipio" in df_produccion.columns:
            df_produccion["id_municipio"] = df_produccion["id_municipio"].astype(str).str.zfill(5)
        else:
            df_produccion = agregar_id_municipio(df_produccion, col_nombre="municipio")
            
        df_estaciones = asignar_estaciones_a_municipios(df_estaciones, df_divipola, fallback_col="municipio")
        
        # Cargar estaciones
        df_estaciones_dim = df_estaciones.rename(columns={
            "codigo": "id_estacion", "nombre": "nombre_estacion", "categoria": "tipo_estacion",
            "latitud": "latitud", "longitud": "longitud", "altitud": "altitud_msnm"
        })
        df_estaciones_dim["latitud"] = pd.to_numeric(df_estaciones_dim["latitud"], errors="coerce")
        df_estaciones_dim["longitud"] = pd.to_numeric(df_estaciones_dim["longitud"], errors="coerce")
        df_estaciones_dim["estado_activa"] = df_estaciones_dim["estado"].astype(str).str.upper() == "ACTIVA"
        cols_estacion = ["id_estacion", "nombre_estacion", "tipo_estacion", "latitud", "longitud", "altitud_msnm", "id_municipio", "estado_activa"]
        df_estaciones_dim = df_estaciones_dim[cols_estacion].dropna(subset=["id_estacion"])
        df_estaciones_dim = df_estaciones_dim.replace({np.nan: None})
        load_dim_estacion_ideam(engine, df_estaciones_dim)

        # ── 5/6. Hechos ──
        progress.update(task, description="[cyan]Cargando hechos de producción y clima...")
        load_all_facts(engine, df_produccion.dropna(subset=["id_municipio"]), pd.DataFrame())
        
        df_clima_mensual = unificar_clima_mensual(df_precip_mensual, df_combinado_mensual)
        if not df_clima_mensual.empty:
            load_fact_clima_mensual(engine, df_clima_mensual)

        # ── 7. Calidad ──
        progress.update(task, description="[cyan]Generando reporte de calidad...")
        reporte = run_quality_report(engine)
        progress.update(task, description="[bold green]ETL CORE Completado.")

    # Mostrar reporte de calidad elegante
    table = Table(title="Reporte de Calidad de Datos", box=None)
    table.add_column("Indicador", style="cyan")
    table.add_column("Valor", justify="right")
    table.add_column("Estado", justify="center")

    for _, row in reporte.iterrows():
        color = "green" if row["estado"] == "OK" else "bold red"
        table.add_row(row["indicador"], str(row["valor"]), f"[{color}]{row['estado']}[/{color}]")
    
    console.print(table)
    return reporte


def run_extended_etl(engine=None):
    console.rule("[bold magenta]PASO 2: ETL EXTENDIDO (Insumos, Suelos, Alertas)")
    
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        task = progress.add_task("Iniciando procesos extendidos...", total=None)

        from load.db import get_engine, init_schema
        from extract.extract_noaa_enso import extract_noaa_enso
        from extract.extract_sipsa import extract_sipsa
        from extract.extract_sipra import extract_sipra
        from clean.clean_precios import normalizar_precios_sipsa, construir_dim_centrales
        from clean.clean_suelo import resumir_aptitud_suelo_por_municipio
        from load.load_dimensions import load_dim_central_abastos, load_dim_region_natural, load_dim_tiempo
        from load.load_facts import (
            load_fact_alerta_enso, load_fact_precios_mayoristas,
            load_fact_aptitud_suelo, load_fact_censo_agropecuario,
            load_fact_precios_insumos
        )
        from extract.extract_insumos import extract_insumos
        from clean.clean_insumos import normalizar_insumos
        from extract.extract_divipola import extract_divipola
        from extract.extract_cna import extract_cna
        
        if engine is None:
            engine = get_engine()
        init_schema(engine)
        load_dim_region_natural(engine)
        load_dim_tiempo(engine)

        # Boletines ENSO (Reemplazado por NOAA API)
        progress.update(task, description="[magenta]Procesando Índice ONI ENSO (NOAA)...")
        df_boletines = extract_noaa_enso()
        if not df_boletines.empty:
            load_fact_alerta_enso(engine, df_boletines)
            # Índices derivados de datos reales: años Niño desde el ONI y SPI/anomalía desde el clima
            from load.derive_clima_indices import actualizar_es_anio_nino, actualizar_indices_precipitacion
            actualizar_es_anio_nino(engine)
            actualizar_indices_precipitacion(engine)

        # Insumos (Usando el extractor robusto con datos sintéticos)
        progress.update(task, description="[magenta]Actualizando Precios de Insumos (IPIA)...")
        df_insumos_raw = extract_insumos()
        if not df_insumos_raw.empty:
            df_insumos = normalizar_insumos(df_insumos_raw)
            if not df_insumos.empty:
                load_fact_precios_insumos(engine, df_insumos)

        # SIPSA
        progress.update(task, description="[magenta]Obteniendo Precios Mayoristas (SIPSA)...")
        df_sipsa_raw = extract_sipsa()
        df_precios = normalizar_precios_sipsa(df_sipsa_raw)
        if not df_precios.empty:
            df_centrales = construir_dim_centrales(df_precios)
            if not df_centrales.empty:
                load_dim_central_abastos(engine, df_centrales)
            load_fact_precios_mayoristas(engine, df_precios)

        # SIPRA (Suelos)
        progress.update(task, description="[magenta]Analizando Aptitud de Suelos (SIPRA)...")
        df_divipola = extract_divipola()
        df_sipra = extract_sipra()
        df_suelo = resumir_aptitud_suelo_por_municipio(df_sipra, df_divipola)
        if not df_suelo.empty:
            load_fact_aptitud_suelo(engine, df_suelo)

        # CNA
        progress.update(task, description="[magenta]Consolidando Censo Agropecuario (CNA)...")
        df_censo = extract_cna()
        if not df_censo.empty:
            load_fact_censo_agropecuario(engine, df_censo)

        progress.update(task, description="[bold green]ETL EXTENDIDO Completado.")


def run_models(engine=None):
    console.rule("[bold yellow]PASO 3: FEATURE STORE Y MACHINE LEARNING")
    failures = []
    
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Construyendo variables para ML...", total=None)
        
        from models.build_features import build_ml_features
        df_features = build_ml_features(engine)
        if df_features.empty:
            raise RuntimeError("No fue posible construir el feature store")
        
        progress.update(task, description="[yellow]Entrenando Modelo: Rendimiento Agrícola...")
        try:
            from models.train_rendimiento import train_and_report as train_rendimiento
            r1 = train_rendimiento(engine=engine)
            logger.info(f"Rendimiento — R²: {r1['metrics']['r2']:.4f}")
        except Exception as exc:
            failures.append(f"rendimiento: {exc}")
            logger.exception("Modelo rendimiento fallo")

        progress.update(task, description="[yellow]Entrenando Modelo: Alerta Climática...")
        try:
            from models.train_alerta_climatica import train_and_report as train_alerta
            r2 = train_alerta(engine=engine)
            logger.info(f"Alerta climática — F1: {r2['metrics']['f1_weighted']:.4f}")
        except Exception as exc:
            failures.append(f"alerta_climatica: {exc}")
            logger.exception("Modelo alerta climatica fallo")

        if failures:
            progress.update(task, description="[bold red]MODELOS IA con errores.")
            raise RuntimeError(" ; ".join(failures))

        progress.update(task, description="[bold green]MODELOS IA Completados.")


def run_precios(engine=None):
    """Precios diarios (SIPSA): delega en run_prices, que ya registra cada paso en ingest_run."""
    from load.db import get_engine
    from run_prices import run_hourly

    console.rule("[bold cyan]PRECIOS DIARIOS (SIPSA)")
    resultado = run_hourly(engine or get_engine())
    console.print(resultado)
    return resultado


# Etapa → función. Cada una queda en ingest_run como `pipeline_<etapa>` (estado, filas, error).
ETAPAS = {"core": run_core_etl, "extended": run_extended_etl, "models": run_models}


def run_etl(mode: str = "all"):
    print_banner()
    from load.db import get_engine
    from load.ingest_log import avisar_frescura, registrar_etapa

    engine = get_engine()

    if mode == "precios":
        run_precios(engine)
    elif mode != "salud":
        etapas = list(ETAPAS) if mode == "all" else [mode]
        for nombre in etapas:
            with registrar_etapa(engine, f"pipeline_{nombre}"):
                ETAPAS[nombre](engine=engine)
        try:   # los reportes de extracción (JSON en disco) se publican en la BD para que la web los lea
            from config.settings import DATA_RAW
            from utils.extraction_quality import sincronizar_reportes

            sincronizar_reportes(engine, DATA_RAW.parent / "quality_reports")
        except Exception:
            logger.exception("No se pudieron sincronizar los reportes de extracción")

    avisar_frescura(engine)   # avisa por webhook si los precios o el pipeline llevan demasiado sin actualizarse

    console.print("\n[bold green][OK] Pipeline finalizado con exito.[/bold green]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Orquestador AgroIA ETL")
    parser.add_argument("--once", action="store_true", help="Ejecuta una vez y sale")
    parser.add_argument(
        "--mode", choices=["core", "extended", "models", "all", "precios", "salud"], default="all",
        help="core/extended/models/all = ETL semanal · precios = ingesta diaria SIPSA · salud = solo revisa la frescura y avisa",
    )
    args = parser.parse_args()

    if args.once:
        run_etl(mode=args.mode)
    else:
        from apscheduler.schedulers.blocking import BlockingScheduler
        scheduler = BlockingScheduler(timezone="America/Bogota")
        scheduler.add_job(run_etl, "cron", day_of_week="mon", hour=2, minute=0, kwargs={"mode": "all"})
        
        console.print(Panel(
            "[bold cyan]MODO SCHEDULER ACTIVO[/bold cyan]\n"
            "Ejecución programada: [yellow]Todos los Lunes a las 02:00 AM (Bogotá)[/yellow]\n"
            "Presione [bold red]Ctrl+C[/bold red] para detener.",
            title="Reloj de Control"
        ))
        
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            console.print("\n[bold red]Scheduler detenido manualmente.[/bold red]")
