# TODO AWS MIGRATION: replace with boto3 S3 put_object() / DynamoDB put_item()
"""
storage.py
==========
Local SQLite-based storage layer simulating AWS S3 (cold) and DynamoDB (hot).

Tables
------
cold_storage  →  simulates S3 (raw payload archive)
hot_storage   →  simulates DynamoDB (indexed routing records for dashboard)

On AWS migration
----------------
  save_cold()  → boto3.client('s3').put_object(Bucket=..., Key=..., Body=...)
  save_hot()   → boto3.resource('dynamodb').Table(...).put_item(Item=...)
  get_recent_hot_records() → DynamoDB Query with ScanIndexForward=False
  get_routing_distribution() → DynamoDB Scan + aggregate
"""

import os
import sqlite3
import json
from datetime import datetime, timezone

_DEFAULT_DB_PATH = os.path.join("data", "processed", "app.db")
_db_path: str    = _DEFAULT_DB_PATH


def init_db(db_path: str = _DEFAULT_DB_PATH) -> None:
    """
    Initialise the SQLite database and create tables if they don't exist.

    Parameters
    ----------
    db_path : str  Path to the .db file (default: data/processed/app.db).
    """
    global _db_path
    _db_path = db_path
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    # --- cold_storage: simulates S3 raw payload archive ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cold_storage (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id   TEXT    NOT NULL,
            timestamp   TEXT    NOT NULL,
            raw_payload TEXT    NOT NULL,  -- JSON string
            stored_at   TEXT    NOT NULL
        )
    """)

    # --- hot_storage: simulates DynamoDB indexed records for the dashboard ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS hot_storage (
            id                       INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id                TEXT    NOT NULL,
            timestamp                TEXT    NOT NULL,
            routing_decision         TEXT    NOT NULL,
            reason                   TEXT    NOT NULL,
            predicted_latency_ms     REAL,
            patient_criticality_score REAL,
            stored_at                TEXT    NOT NULL
        )
    """)

    con.commit()
    con.close()


def _get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with row_factory for dict-like rows."""
    os.makedirs(os.path.dirname(_db_path), exist_ok=True)
    con = sqlite3.connect(_db_path)
    con.row_factory = sqlite3.Row
    return con


def save_cold(device_id: str, timestamp: str, raw_payload: dict) -> None:
    """
    Save a raw telemetry payload to cold storage (simulates S3).

    # TODO AWS MIGRATION: replace with boto3 S3 put_object()
    #   s3 = boto3.client('s3')
    #   s3.put_object(Bucket=BUCKET, Key=f"{device_id}/{timestamp}.json",
    #                 Body=json.dumps(raw_payload))

    Parameters
    ----------
    device_id   : str   Device identifier.
    timestamp   : str   ISO8601 event timestamp.
    raw_payload : dict  Full raw telemetry record to archive.
    """
    con = _get_connection()
    con.execute(
        """INSERT INTO cold_storage (device_id, timestamp, raw_payload, stored_at)
           VALUES (?, ?, ?, ?)""",
        (device_id, timestamp, json.dumps(raw_payload), datetime.now(timezone.utc).isoformat()),
    )
    con.commit()
    con.close()


def save_hot(record: dict) -> None:
    """
    Save a processed routing record to hot storage (simulates DynamoDB).

    # TODO AWS MIGRATION: replace with boto3 DynamoDB put_item()
    #   table = boto3.resource('dynamodb').Table(TABLE_NAME)
    #   table.put_item(Item=record)

    Parameters
    ----------
    record : dict  Must contain: device_id, timestamp, routing_decision, reason,
                   predicted_latency_ms, patient_criticality_score.
    """
    con = _get_connection()
    con.execute(
        """INSERT INTO hot_storage
               (device_id, timestamp, routing_decision, reason,
                predicted_latency_ms, patient_criticality_score, stored_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            record.get("device_id",                "UNKNOWN"),
            record.get("timestamp",                datetime.now(timezone.utc).isoformat()),
            record.get("routing_decision",         "UNKNOWN"),
            record.get("reason",                   "unknown"),
            record.get("predicted_latency_ms",     0.0),
            record.get("patient_criticality_score", 0.0),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    con.commit()
    con.close()


def get_recent_hot_records(limit: int = 100) -> list:
    """
    Retrieve the most recent routing records for the dashboard.

    Returns
    -------
    list[dict]  Records ordered by stored_at descending.
    """
    con = _get_connection()
    rows = con.execute(
        """SELECT device_id, timestamp, routing_decision, reason,
                  predicted_latency_ms, patient_criticality_score, stored_at
           FROM hot_storage
           ORDER BY stored_at DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    con.close()
    return [dict(row) for row in rows]


def get_routing_distribution() -> dict:
    """
    Return a count of EDGE vs CLOUD routing decisions for all time.

    Returns
    -------
    dict  e.g. {"EDGE": 42, "CLOUD": 58}
    """
    con = _get_connection()
    rows = con.execute(
        """SELECT routing_decision, COUNT(*) AS cnt
           FROM hot_storage
           GROUP BY routing_decision"""
    ).fetchall()
    con.close()
    return {row["routing_decision"]: row["cnt"] for row in rows}


if __name__ == "__main__":
    init_db()
    save_cold("ECG-101", "2026-09-22T10:15:32Z", {"bandwidth_mbps": 42.3})
    save_hot({
        "device_id":                 "ECG-101",
        "timestamp":                 "2026-09-22T10:15:32Z",
        "routing_decision":          "EDGE",
        "reason":                    "override_critical_patient",
        "predicted_latency_ms":      210.5,
        "patient_criticality_score": 9.5,
    })
    print("Recent records:", get_recent_hot_records(5))
    print("Distribution:  ", get_routing_distribution())
