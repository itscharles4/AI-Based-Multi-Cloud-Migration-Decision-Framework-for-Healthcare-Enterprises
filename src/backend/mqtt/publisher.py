"""
scripts/mqtt_publisher.py
==========================
Test MQTT publisher — simulates IoMT devices sending readings.
Use this to test the MQTT consumer without real hardware.

Usage:
  # Publish 100 readings from all 5 devices (default):
  python scripts/mqtt_publisher.py

  # Publish emergency events only:
  python scripts/mqtt_publisher.py --mode emergency

  # Publish continuously:
  python scripts/mqtt_publisher.py --continuous
"""

import argparse
import json
import random
import time
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import paho.mqtt.client as mqtt
from backend.core.config import settings

DEVICES = ["ECG-101", "ECG-102", "O2-201", "WEARABLE-301", "WEARABLE-302"]


def make_reading(device_id: str, mode: str = "normal") -> dict:
    """Generate a synthetic telemetry reading."""
    if mode == "emergency":
        # High criticality, degraded network
        return {
            "timestamp":                datetime.now(timezone.utc).isoformat(),
            "device_id":                device_id,
            "bandwidth_mbps":           random.uniform(5, 20),
            "packet_loss_pct":          random.uniform(8, 20),
            "jitter_ms":                random.uniform(50, 100),
            "signal_strength_dbm":      random.uniform(-85, -75),
            "current_latency_ms":       random.uniform(200, 400),
            "patient_criticality_score": random.uniform(9.0, 10.0),
            "cloud_cost_index":         random.uniform(0.3, 0.7),
        }
    elif mode == "degraded":
        # High latency but routine patient
        return {
            "timestamp":                datetime.now(timezone.utc).isoformat(),
            "device_id":                device_id,
            "bandwidth_mbps":           random.uniform(10, 30),
            "packet_loss_pct":          random.uniform(5, 12),
            "jitter_ms":                random.uniform(30, 80),
            "signal_strength_dbm":      random.uniform(-80, -70),
            "current_latency_ms":       random.uniform(280, 500),
            "patient_criticality_score": random.uniform(1.0, 5.0),
            "cloud_cost_index":         random.uniform(0.2, 0.5),
        }
    else:
        # Normal network, routine patient
        return {
            "timestamp":                datetime.now(timezone.utc).isoformat(),
            "device_id":                device_id,
            "bandwidth_mbps":           random.uniform(40, 100),
            "packet_loss_pct":          random.uniform(0, 2),
            "jitter_ms":                random.uniform(2, 15),
            "signal_strength_dbm":      random.uniform(-65, -50),
            "current_latency_ms":       random.uniform(10, 60),
            "patient_criticality_score": random.uniform(1.0, 8.0),
            "cloud_cost_index":         random.uniform(0.1, 0.9),
        }


def main():
    parser = argparse.ArgumentParser(description="MQTT device simulator")
    parser.add_argument("--mode", choices=["normal", "emergency", "degraded", "mixed"],
                        default="mixed", help="Simulation mode")
    parser.add_argument("--count", type=int, default=100, help="Number of readings to send")
    parser.add_argument("--interval", type=float, default=0.5, help="Seconds between readings")
    parser.add_argument("--continuous", action="store_true", help="Run continuously")
    args = parser.parse_args()

    client = mqtt.Client(client_id="telemedicine-test-publisher")
    print(f"[publisher] Connecting to {settings.MQTT_HOST}:{settings.MQTT_PORT}...")
    client.connect(settings.MQTT_HOST, settings.MQTT_PORT)
    client.loop_start()
    print(f"[publisher] Connected. Mode: {args.mode}")

    sent = 0
    try:
        while args.continuous or sent < args.count:
            device_id = random.choice(DEVICES)
            topic     = f"telemedicine/devices/{device_id}"

            if args.mode == "mixed":
                mode = random.choices(
                    ["normal", "emergency", "degraded"],
                    weights=[0.85, 0.05, 0.10]
                )[0]
            else:
                mode = args.mode

            reading = make_reading(device_id, mode)
            payload = json.dumps(reading)

            result = client.publish(topic, payload, qos=1)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                sent += 1
                icon = "🚨" if mode == "emergency" else "⚠️" if mode == "degraded" else "✓"
                print(f"  {icon} [{sent:04d}] {device_id} ({mode}) lat={reading['current_latency_ms']:.0f}ms")
            else:
                print(f"  [ERR] Publish failed rc={result.rc}")

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print(f"\n[publisher] Stopped after {sent} messages")

    client.loop_stop()
    client.disconnect()
    print(f"[publisher] Done. Sent {sent} readings.")


if __name__ == "__main__":
    main()
