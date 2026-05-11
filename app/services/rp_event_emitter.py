import requests
from flask import current_app

def emit_event(event_type: str, payload: dict):
    """Send a structured event to the analytics ingestion endpoint."""
    config = current_app.config
    url = config.get('EVENT_INGESTION_URL')
    token = config.get('EVENT_SERVICE_TOKEN')

    if not url:
        return

    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    body = {
        "event_type": event_type,
        "payload": payload,
        "timestamp": payload.get("timestamp", "")
    }

    try:
        resp = requests.post(url, json=body, headers=headers, timeout=2)
        resp.raise_for_status()
    except Exception as e:
        current_app.logger.error(f"Event emission failed: {e}")