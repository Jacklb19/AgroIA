FROM python:3.11-slim

# libgomp1: requerido en runtime por xgboost/scikit-learn (OpenMP) en imágenes slim.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# run_pipeline.py crea data/, logs/, etc. al importar config.settings si no existen.
CMD ["python", "run_pipeline.py", "--mode", "all", "--once"]
