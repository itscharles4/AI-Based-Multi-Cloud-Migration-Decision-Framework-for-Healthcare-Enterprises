"""
scripts/seed_db.py
==================
Seed the database with:
  1. Default admin user (admin@telemedicine.local / Admin1234!)
  2. A sample doctor user
  3. A sample auditor user
  4. 200 sample routing decisions for dashboard demo

Run with:
  python scripts/seed_db.py

Run inside Docker:
  docker compose exec api python scripts/seed_db.py
"""

import asyncio
import random
import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select
from backend.core.database    import init_db, AsyncSessionLocal
from backend.core.security    import hash_password, UserRole
from backend.models.user      import User
from backend.models.routing   import RoutingDecision
from backend.models.telemetry import TelemetryReading


DEVICES    = ["ECG-101", "ECG-102", "O2-201", "WEARABLE-301", "WEARABLE-302"]
REASONS    = [
    ("override_critical_patient", "EDGE"),
    ("network_degradation_veto",  "EDGE"),
    ("ahp_decision",              "CLOUD"),
    ("ahp_decision",              "EDGE"),
]
RISKS = ["LOW", "MEDIUM", "HIGH"]


async def seed():
    print("[seed] Initialising database...")
    await init_db()

    async with AsyncSessionLocal() as db:
        # ── Seed Users ──────────────────────────────────────────────────────
        users_to_create = [
            {
                "username":   "admin",
                "email":      "admin@telemedicine.local",
                "full_name":  "System Administrator",
                "password":   "Admin1234!",
                "role":       UserRole.ADMIN,
                "department": "IT",
            },
            {
                "username":   "dr.sharma",
                "email":      "dr.sharma@telemedicine.local",
                "full_name":  "Dr. Priya Sharma",
                "password":   "Doctor1234!",
                "role":       UserRole.DOCTOR,
                "department": "Cardiology",
            },
            {
                "username":   "auditor",
                "email":      "auditor@telemedicine.local",
                "full_name":  "HIPAA Compliance Officer",
                "password":   "Auditor1234!",
                "role":       UserRole.AUDITOR,
                "department": "Compliance",
            },
        ]

        created_users = []
        for u in users_to_create:
            existing = await db.execute(select(User).where(User.username == u["username"]))
            if existing.scalar_one_or_none():
                print(f"  [skip] User '{u['username']}' already exists")
                continue

            user = User(
                username        = u["username"],
                email           = u["email"],
                full_name       = u["full_name"],
                hashed_password = hash_password(u["password"]),
                role            = u["role"],
                department      = u["department"],
            )
            db.add(user)
            created_users.append(u["username"])

        await db.flush()
        print(f"  [ok] Created {len(created_users)} users: {created_users}")

        # ── Seed Sample Routing Decisions ───────────────────────────────────
        existing_count_result = await db.execute(select(RoutingDecision))
        existing_count = len(existing_count_result.scalars().all())

        if existing_count >= 200:
            print(f"  [skip] {existing_count} routing decisions already exist")
        else:
            print("  [seed] Generating 200 sample routing decisions...")
            now = datetime.now(timezone.utc)
            rows = []

            for i in range(200):
                device_id   = random.choice(DEVICES)
                ts          = now - timedelta(hours=random.uniform(0, 48))
                criticality = random.choices(
                    [random.uniform(1, 8), random.uniform(9, 10)],
                    weights=[0.92, 0.08]
                )[0]

                if criticality >= 9.0:
                    reason, decision = "override_critical_patient", "EDGE"
                elif random.random() < 0.1:
                    reason, decision = "network_degradation_veto", "EDGE"
                else:
                    reason, decision = "ahp_decision", random.choice(["EDGE", "CLOUD"])

                pred_lat = random.uniform(10, 400)
                risk     = "LOW" if pred_lat < 75 else "MEDIUM" if pred_lat < 150 else "HIGH"

                rows.append(RoutingDecision(
                    timestamp                 = ts,
                    device_id                 = device_id,
                    predicted_latency_ms      = round(pred_lat, 2),
                    network_degradation_risk  = risk,
                    patient_criticality_score = round(criticality, 2),
                    current_cloud_cost_index  = round(random.uniform(0.1, 0.9), 2),
                    routing_decision          = decision,
                    reason                    = reason,
                    edge_score                = round(random.uniform(0.3, 0.9), 4),
                    cloud_score               = round(random.uniform(0.1, 0.7), 4),
                    execution_status          = "processed_at_edge" if decision == "EDGE" else "processed_in_cloud",
                    alerted                   = 1 if reason == "override_critical_patient" else 0,
                    user_id                   = None,
                    request_source            = random.choice(["http", "mqtt"]),
                ))

            db.add_all(rows)
            print(f"  [ok] Added {len(rows)} routing decisions")

        await db.commit()

    print("\n[seed] Complete! Default credentials:")
    print("  Admin   : admin / Admin1234!")
    print("  Doctor  : dr.sharma / Doctor1234!")
    print("  Auditor : auditor / Auditor1234!")
    print("\nStart the API: uvicorn backend.app:app --reload")
    print("Open API docs: http://localhost:8000/docs")


if __name__ == "__main__":
    asyncio.run(seed())
