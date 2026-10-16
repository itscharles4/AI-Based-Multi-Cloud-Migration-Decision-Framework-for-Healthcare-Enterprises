"""
backend/mqtt/consumer.py
========================
MQTT consumer service — subscribes to the Mosquitto broker and
feeds IoMT telemetry directly into the pipeline.

This replaces the simulate_stream.py approach with a real MQTT
subscription — the same protocol IoT devices (ECG monitors,
wearable sensors) actually use in hospitals.

Topic structure:
  telemedicine/devices/{device_id}  → JSON telemetry reading

Usage (standalone, outside Docker):
  python -m backend.mqtt.consumer

Usage (Docker):
  docker compose up mqtt-consumer  ← starts automatically
"""

import asyncio
import json
import logging
import os
import sys
from collections import defaultdict, deque
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.core.config   import settings
from backend.core.database import AsyncSessionLocal, init_db
from backend.services.pipeline import run_pipeline

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

# ── Sliding window buffer per device ─────────────────────────────────────────
WINDOW_SIZE = 20
_device_buffers: dict[str, deque] = defaultdict(lambda: deque(maxlen=WINDOW_SIZE))
_loop: asyncio.AbstractEventLoop = None


# ── MQTT callbacks ────────────────────────────────────────────────────────────
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("[mqtt] Connected to broker %s:%s", settings.MQTT_HOST, settings.MQTT_PORT)
        client.subscribe(settings.MQTT_TOPIC)
        logger.info("[mqtt] Subscribed to topic: %s", settings.MQTT_TOPIC)
    else:
        logger.error("[mqtt] Connection failed with code %d", rc)


def on_message(client, userdata, msg):
    """
    Called by paho-mqtt on every received message.
    Runs in the paho thread — schedules async work on the event loop.
    """
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning("[mqtt] Malformed JSON from topic %s: %s", msg.topic, exc)
        return

    device_id = payload.get("device_id") or msg.topic.split("/")[-1]
    if not device_id:
        logger.warning("[mqtt] Missing device_id in payload from %s", msg.topic)
        return

    # Add timestamp if absent
    if "timestamp" not in payload:
        payload["timestamp"] = datetime.now(timezone.utc).isoformat()

    # Push into sliding window buffer
    _device_buffers[device_id].append(payload)
    buf_size = len(_device_buffers[device_id])

    logger.debug("[mqtt] device=%s buffer=%d/%d", device_id, buf_size, WINDOW_SIZE)

    # When buffer is full, trigger pipeline
    if buf_size == WINDOW_SIZE:
        window = list(_device_buffers[device_id])
        # Extract context from most recent payload
        criticality = float(payload.get("patient_criticality_score", 2.0))
        cost_index  = float(payload.get("cloud_cost_index", 0.3))

        # Schedule async pipeline on the event loop (thread-safe)
        if _loop and not _loop.is_closed():
            asyncio.run_coroutine_threadsafe(
                _process_window(window, criticality, cost_index, device_id),
                _loop,
            )


def on_disconnect(client, userdata, rc):
    if rc != 0:
        logger.warning("[mqtt] Unexpected disconnect (rc=%d). Will auto-reconnect.", rc)


# ── Async pipeline trigger ────────────────────────────────────────────────────
async def _process_window(
    window: list,
    criticality: float,
    cost_index: float,
    device_id: str,
):
    """Run the full pipeline for a completed MQTT window."""
    try:
        async with AsyncSessionLocal() as db:
            result = await run_pipeline(
                window                    = window,
                patient_criticality_score = criticality,
                current_cloud_cost_index  = cost_index,
                db                        = db,
                user_id                   = None,
                request_source            = "mqtt",
            )
            await db.commit()

        logger.info(
            "[mqtt-pipeline] device=%s → %s (%s) latency=%.1fms",
            device_id,
            result["routing_decision"],
            result["reason"],
            result["predicted_latency_ms"],
        )
    except Exception as exc:
        logger.error("[mqtt-pipeline] Pipeline failed for device=%s: %s", device_id, exc)


# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    global _loop
    _loop = asyncio.get_running_loop()

    # Initialise DB on startup
    await init_db()

    # Create MQTT client
    client = mqtt.Client(client_id=settings.MQTT_CLIENT_ID)
    client.on_connect    = on_connect
    client.on_message    = on_message
    client.on_disconnect = on_disconnect

    # Connect
    logger.info("[mqtt] Connecting to %s:%s...", settings.MQTT_HOST, settings.MQTT_PORT)
    client.connect(settings.MQTT_HOST, settings.MQTT_PORT, keepalive=60)
    client.loop_start()   # starts paho thread

    logger.info("[mqtt] Consumer running. Press Ctrl+C to stop.")
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("[mqtt] Shutting down...")
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
