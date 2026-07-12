import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    handlers=[logging.FileHandler('logs/etl_run.log', encoding='utf-8'), logging.StreamHandler()])
from load.db import get_engine
from extract.extract_openmeteo import extract_openmeteo_clima
from load.load_facts import fill_fact_clima_from_openmeteo
engine = get_engine()
df = extract_openmeteo_clima(engine)
print('Filas obtenidas:', len(df))
if not df.empty:
    fill_fact_clima_from_openmeteo(engine, df)
    print('Hecho.')
else:
    print('Sin datos.')
