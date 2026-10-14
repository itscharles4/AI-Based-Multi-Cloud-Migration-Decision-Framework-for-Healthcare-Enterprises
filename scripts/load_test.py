"""Load test for the Telemedicine Workload Offloader API.

Usage:
    # 1. Start the API server first:
    #    docker compose up -d   OR   uvicorn backend.app:app --reload

    # 2. Set credentials (use a 'service' role account):
    set LOCUST_USER=service_account
    set LOCUST_PASSWORD=your_password

    # 3. Run the load test:
    locust -f scripts/load_test.py --host http://localhost:8000

    # 4. Headless mode (for CI / pre-deploy check):
    locust -f scripts/load_test.py --host http://localhost:8000 \\
           --headless -u 50 -r 5 --run-time 60s \\
           --csv results/load_test_50users

Record p95 latency and error rate at 10 / 50 / 200 concurrent users for the report.
Target SLA: p95 < 200ms at 50 users, error rate < 1%.
"""
import itertools
import os
import random
from datetime import datetime, timedelta, timezone

from locust import HttpUser, between, task

_counter = itertools.count()

# 5% of readings simulate network degradation (high latency)
DEGRADATION_PROBABILITY = 0.05

# 3% of readings trigger emergency override (criticality >= 9.0)
EMERGENCY_PROBABILITY = 0.03


class TelemedicineDevice(HttpUser):
    """Simulates one IoMT device sending telemetry to the API."""

    wait_time = between(0.1, 0.5)  # realistic device polling interval

    def on_start(self) -> None:
        """Authenticate once per virtual user, reuse token for all requests."""
        resp = self.client.post(
            "/auth/login",
            data={
                "username": os.environ.get("LOCUST_USER", "service_account"),
                "password": os.environ.get("LOCUST_PASSWORD", "service_password"),
            },
            name="POST /auth/login",
        )
        if resp.status_code == 200:
            self.client.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"
        else:
            raise Exception(f"Login failed: {resp.status_code} {resp.text}")

        # Assign a unique simulated device ID to this user
        self.device_id = f"LOAD-{random.randint(0, 99):03d}"

    @task(10)
    def ingest_normal(self) -> None:
        """Normal telemetry — expected to route to CLOUD most of the time."""
        ts = datetime.now(timezone.utc) - timedelta(microseconds=next(_counter))
        self.client.post(
            "/ingest",
            name="POST /ingest [normal]",
            json={
                "device_id": self.device_id,
                "timestamp": ts.isoformat(),
                "bandwidth_mbps":       round(random.uniform(10.0, 100.0), 2),
                "packet_loss_pct":      round(abs(random.gauss(0.3, 0.2)), 3),
                "jitter_ms":            round(abs(random.gauss(5.0, 2.0)), 2),
                "signal_strength_dbm":  round(random.uniform(-80.0, -40.0), 1),
                "current_latency_ms":   round(abs(random.gauss(40.0, 10.0)), 1),
                "patient_criticality_score": round(random.uniform(1.0, 5.0), 1),
                "cloud_cost_index":     round(random.uniform(0.2, 0.8), 3),
            },
        )

    @task(1)
    def ingest_degraded(self) -> None:
        """Network-degraded telemetry — expected to trigger EDGE + WARNING alert."""
        ts = datetime.now(timezone.utc) - timedelta(microseconds=next(_counter))
        self.client.post(
            "/ingest",
            name="POST /ingest [degraded]",
            json={
                "device_id": self.device_id,
                "timestamp": ts.isoformat(),
                "bandwidth_mbps":       round(random.uniform(0.5, 3.0), 2),
                "packet_loss_pct":      round(random.uniform(5.0, 20.0), 2),
                "jitter_ms":            round(random.uniform(80.0, 200.0), 1),
                "signal_strength_dbm":  round(random.uniform(-100.0, -85.0), 1),
                "current_latency_ms":   round(random.uniform(250.0, 450.0), 1),
                "patient_criticality_score": round(random.uniform(3.0, 7.0), 1),
                "cloud_cost_index":     round(random.uniform(0.6, 1.0), 3),
            },
        )

    @task(1)
    def ingest_emergency(self) -> None:
        """Emergency patient — criticality >= 9.0, forces EDGE override."""
        ts = datetime.now(timezone.utc) - timedelta(microseconds=next(_counter))
        self.client.post(
            "/ingest",
            name="POST /ingest [emergency]",
            json={
                "device_id": self.device_id,
                "timestamp": ts.isoformat(),
                "bandwidth_mbps":       round(random.uniform(5.0, 50.0), 2),
                "packet_loss_pct":      round(abs(random.gauss(1.0, 0.5)), 3),
                "jitter_ms":            round(abs(random.gauss(10.0, 5.0)), 2),
                "signal_strength_dbm":  round(random.uniform(-75.0, -50.0), 1),
                "current_latency_ms":   round(abs(random.gauss(60.0, 15.0)), 1),
                "patient_criticality_score": round(random.uniform(9.0, 10.0), 1),
                "cloud_cost_index":     round(random.uniform(0.1, 0.5), 3),
            },
        )

    @task(2)
    def check_health(self) -> None:
        """Liveness probe — should always return 200."""
        self.client.get("/health", name="GET /health")

    @task(1)
    def get_stats(self) -> None:
        """Routing statistics endpoint."""
        self.client.get("/stats", name="GET /stats")
