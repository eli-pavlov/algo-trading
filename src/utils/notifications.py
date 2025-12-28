import requests
import os
import json
from src.utils.logger import setup_logger

logger = setup_logger("Notifier")

def send_alert(data):
    """
    Sends a formatted JSON payload to the Webhook URL defined in .env
    """
    url = os.getenv("WEBHOOK_URL")
    if not url:
        logger.warning("No WEBHOOK_URL set. Skipping alert.")
        return

    # Format dict into a readable string block
    text_block = "\n".join([f"*{key}:* {value}" for key, value in data.items()])
    payload = {"text": text_block}

    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to send webhook: {e}")