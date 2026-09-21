"""
run_prices.py — Orquestador de precios mayoristas diarios (SIPSA - DANE).

Uso:
  python run_prices.py --mode init               # crea/actualiza tablas y vista de precios
  python run_prices.py --mode backfill           # historial completo por SOAP (una vez, ~300 MB)
  python run_prices.py --mode soap [--dias 14]   # actualización por SOAP (últimos N días)
  python run_prices.py --mode hourly             # sondeo horario (Railway cron: 0 * * * *)
  python run_prices.py --mode informe            # regenera el informe diario del último día con datos
  python run_prices.py --mode forecast           # reentrena (con backtest) y pronostica 1-10 días hábiles

DANE publica una vez por día hábil, así que "cada hora" significa revisar si hay
dato nuevo:
  1. Excel diario (HEAD ~1 KB): si cambió, se descarga y se cargan ~16 mercados.
  2. El Excel no trae Pasto, mín/máx ni varios mercados: si el SOAP va atrasado
     respecto al Excel, se hace una carga incremental por SOAP (reintento cada 2 h).
  3. Una vez por semana se reconcilia el historial completo por SOAP.
"""
import argparse
import logging
import sys
from datetime import date, datetime, timedelta, timezone

from config.settings import LOGS_DIR

logger = logging.getLogger("precios")

FUENTE_EXCEL = "sipsa_excel"
FUENTE_SOAP = "sipsa_soap"
FUENTE_FORECAST = "forecast_precio"
SOAP_VENTANA_DIAS = 7          # cuántos días atrás re-cargar en una actualización incremental
SOAP_REINTENTO = timedelta(hours=2)
RECONCILIACION = timedelta(days=7)


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


# ── Pasos ────────────────────────────────────────────────────────────────
def run_soap(engine, desde: date | None) -> dict:
    """Carga por SOAP. desde=None recarga todo el historial (backfill / reconciliación)."""
    from extract.extract_sipsa_soap import extract_sipsa_soap
    from load.load_precios import cargar_precios, cerrar_run, iniciar_run

    ref = "full" if desde is None else f"desde={desde.isoformat()}"
    id_run = iniciar_run(engine, FUENTE_SOAP, ref)
    try:
        df = extract_sipsa_soap(desde=desde)
        n = cargar_precios(engine, df, "soap")
        fecha_max = df["fecha"].max().date() if not df.empty else None
        cerrar_run(engine, id_run, "ok", filas_nuevas=n, fecha_dato_max=fecha_max)
        return {"status": "ok", "ref": ref, "filas": n, "fecha_dato_max": fecha_max}
    except Exception as exc:
        cerrar_run(engine, id_run, "error", error=repr(exc))
        raise


def run_excel(engine, hoy: date | None = None) -> dict:
    """Sondeo del boletín diario: HEAD siempre; descarga y carga solo si hay archivo nuevo."""
    from extract.extract_sipsa_diario import buscar_ultimo_boletin, extract_sipsa_diario, token_fecha
    from load.load_precios import cargar_precios, cerrar_run, iniciar_run, ultimo_run

    meta = buscar_ultimo_boletin(hoy)
    if meta is None:
        id_run = iniciar_run(engine, FUENTE_EXCEL, None)
        cerrar_run(engine, id_run, "sin_cambios", error="Sin boletin publicado en los ultimos dias")
        logger.warning("SIPSA Excel: no hay boletín publicado en los últimos días")
        return {"status": "sin_boletin", "fecha": None}

    ref = token_fecha(meta.fecha)
    previo = ultimo_run(engine, FUENTE_EXCEL, status="ok", source_ref=ref)
    id_run = iniciar_run(engine, FUENTE_EXCEL, ref)

    if previo and meta.last_modified and previo["source_last_modified"] == meta.last_modified:
        cerrar_run(engine, id_run, "sin_cambios", fecha_dato_max=meta.fecha, source_last_modified=meta.last_modified)
        logger.info("SIPSA Excel %s sin cambios (Last-Modified %s)", ref, meta.last_modified)
        return {"status": "sin_cambios", "fecha": meta.fecha}

    try:
        df = extract_sipsa_diario(meta)
        n = cargar_precios(engine, df, "excel", crear_mercados=False)
        cerrar_run(
            engine, id_run, "ok", filas_nuevas=n, fecha_dato_max=meta.fecha,
            source_last_modified=meta.last_modified,
        )
        return {"status": "ok", "fecha": meta.fecha, "filas": n}
    except Exception as exc:
        cerrar_run(engine, id_run, "error", error=repr(exc))
        raise


def run_soap_si_corresponde(engine, fecha_esperada: date | None, ahora: datetime | None = None) -> dict:
    """Decide si toca una carga por SOAP (reconciliación semanal o puesta al día)."""
    from load.load_precios import fecha_max_precios, ultimo_run

    ahora = ahora or _ahora()
    max_soap = fecha_max_precios(engine, "soap")
    if max_soap is None:
        logger.warning("Sin historial SOAP en la base: ejecuta `python run_prices.py --mode backfill`")
        return {"status": "omitido", "motivo": "sin_backfill"}

    ult_full = ultimo_run(engine, FUENTE_SOAP, status="ok", source_ref="full")
    if ult_full is None or ahora - ult_full["finished_at"] >= RECONCILIACION:
        logger.info("Reconciliación semanal del historial completo por SOAP")
        return run_soap(engine, None)

    if fecha_esperada and max_soap < fecha_esperada:
        ult = ultimo_run(engine, FUENTE_SOAP)
        if ult is None or ahora - ult["started_at"] >= SOAP_REINTENTO:
            logger.info("SOAP atrasado (%s < %s): carga incremental", max_soap, fecha_esperada)
            return run_soap(engine, max_soap - timedelta(days=SOAP_VENTANA_DIAS))
        return {"status": "espera", "motivo": "reintento reciente"}

    return {"status": "al_dia", "fecha_dato_max": max_soap}


def run_informe(engine, fecha: date | None = None, solo_si_pendiente: bool = False) -> dict:
    """Genera el informe diario. Un fallo aquí no debe tumbar la ingesta (se registra y se sigue)."""
    from models.informe_precios import generar_informe, informe_pendiente

    try:
        if solo_si_pendiente and not informe_pendiente(engine):
            return {"status": "al_dia"}
        informe = generar_informe(engine, fecha)
        return {"status": "ok" if informe else "sin_datos", "fecha": informe["fecha"] if informe else None}
    except Exception as exc:
        logger.exception("Informe diario falló")
        return {"status": "error", "error": repr(exc)}


def run_forecast(engine, solo_si_pendiente: bool = False, forzar_backtest: bool = False) -> dict:
    """
    Pronóstico a 1-10 días hábiles. Con solo_si_pendiente solo corre cuando hay un día de datos
    más reciente que el usado en el último pronóstico. Un fallo no debe tumbar la ingesta.
    """
    from load.load_precios import cerrar_run, fecha_max_precios, iniciar_run, ultimo_run
    from models.train_precio_forecast import forecast_y_guardar

    try:
        fecha_max = fecha_max_precios(engine)
        if solo_si_pendiente:
            previo = ultimo_run(engine, FUENTE_FORECAST, status="ok")
            if previo and previo["fecha_dato_max"] and fecha_max and previo["fecha_dato_max"] >= fecha_max:
                return {"status": "al_dia"}
        id_run = iniciar_run(engine, FUENTE_FORECAST, None)
        try:
            res = forecast_y_guardar(engine, forzar_backtest=forzar_backtest)
        except Exception as exc:
            cerrar_run(engine, id_run, "error", error=repr(exc))
            raise
        cerrar_run(
            engine, id_run, "ok" if res.get("status") == "ok" else "sin_cambios",
            filas_nuevas=res.get("predicciones"), fecha_dato_max=res.get("fecha_dato_max"),
        )
        return res
    except Exception as exc:
        logger.exception("Pronóstico de precios falló")
        return {"status": "error", "error": repr(exc)}


def run_hourly(engine) -> dict:
    from load.db import init_schema_precios

    from load.ingest_log import avisar_frescura
    from utils.alertas import enviar_alerta

    init_schema_precios(engine)
    excel = run_excel(engine)
    soap = run_soap_si_corresponde(engine, excel.get("fecha"))
    forecast = run_forecast(engine, solo_si_pendiente=True)
    informe = run_informe(engine, solo_si_pendiente=True)
    resultado = {"excel": excel, "soap": soap, "forecast": forecast, "informe": informe}

    # El pronóstico y el informe no tumban la ingesta, pero un fallo sostenido debe enterarse alguien.
    fallos = {paso: r.get("error") for paso, r in resultado.items() if r.get("status") == "error"}
    if fallos:
        enviar_alerta("Fallo parcial en el job horario de precios", "; ".join(f"{p}: {e}" for p, e in fallos.items()), nivel="aviso")
    avisar_frescura(engine)
    return resultado


# ── CLI ──────────────────────────────────────────────────────────────────
def _configurar_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(LOGS_DIR / "prices_run.log", encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Orquestador de precios diarios SIPSA")
    parser.add_argument("--mode", choices=["init", "backfill", "soap", "hourly", "informe", "forecast"], required=True)
    parser.add_argument("--dias", type=int, default=None, help="Solo los últimos N días (backfill/soap)")
    args = parser.parse_args(argv)

    _configurar_logging()
    from load.db import get_engine, init_schema_precios

    try:
        engine = get_engine()
        if args.mode == "init":
            init_schema_precios(engine, force=True)
            logger.info("Esquema de precios listo")
            return 0

        init_schema_precios(engine)
        if args.mode in ("backfill", "soap"):
            defecto = None if args.mode == "backfill" else SOAP_VENTANA_DIAS * 2
            dias = args.dias if args.dias is not None else defecto
            desde = date.today() - timedelta(days=dias) if dias else None
            resultado = run_soap(engine, desde)
        elif args.mode == "informe":
            resultado = run_informe(engine)
        elif args.mode == "forecast":
            resultado = run_forecast(engine, forzar_backtest=True)
        else:
            resultado = run_hourly(engine)
        logger.info("Resultado: %s", resultado)
        return 0
    except Exception as exc:
        logger.exception("Falló run_prices (%s)", args.mode)
        from utils.alertas import enviar_alerta

        enviar_alerta(f"Falló run_prices ({args.mode})", f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
