"""
alertas.py — Aviso operativo por webhook (opcional).

Si ALERT_WEBHOOK_URL está definida, `enviar_alerta` hace un POST JSON. Slack y Teams leen "text"; Discord lee
"content": se envían ambos. Nunca lanza excepciones: una alerta que falla no debe tumbar el pipeline.
"""
from __future__ import annotations

import logging

import requests

from config.settings import ALERT_WEBHOOK_URL

logger = logging.getLogger(__name__)

_ICONO = {"error": "🔴", "aviso": "🟠", "info": "🟢"}


def enviar_alerta(titulo: str, detalle: str = "", nivel: str = "error", url: str | None = None) -> bool:
    """Devuelve True si el webhook aceptó el mensaje; False si no hay webhook configurado o falló el envío."""
    destino = url or ALERT_WEBHOOK_URL
    if not destino:
        logger.info("Alerta (sin webhook configurado): %s — %s", titulo, detalle)
        return False
    mensaje = f"{_ICONO.get(nivel, '')} AgroIA · {titulo}"
    if detalle:
        mensaje += f"\n{detalle[:1500]}"
    try:
        r = requests.post(destino, json={"text": mensaje, "content": mensaje[:1900]}, timeout=10)
        r.raise_for_status()
        return True
    except requests.RequestException as exc:
        logger.warning("No se pudo enviar la alerta al webhook: %s", exc)
        return False
