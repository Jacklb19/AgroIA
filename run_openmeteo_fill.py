"""Rellena fact_clima_mensual con Open-Meteo donde el IDEAM no tiene datos. Uso: python run_openmeteo_fill.py"""
import logging

from config.settings import LOGS_DIR


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.FileHandler(LOGS_DIR / "etl_run.log", encoding="utf-8"), logging.StreamHandler()],
    )
    from extract.extract_openmeteo import extract_openmeteo_clima
    from load.db import get_engine
    from load.load_facts import fill_fact_clima_from_openmeteo

    engine = get_engine()
    df = extract_openmeteo_clima(engine)
    print("Filas obtenidas:", len(df))
    if df.empty:
        print("Sin datos.")
        return
    fill_fact_clima_from_openmeteo(engine, df)
    print("Hecho.")


if __name__ == "__main__":
    main()
