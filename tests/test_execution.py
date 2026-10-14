"""
test_execution.py
=================
Pytest unit tests for the Execution Layer (Rani's module).

Tests cover:
  1. auth.py   — login success/failure, token verification, expiry, logout
  2. storage.py — init_db, save_cold, save_hot, get_recent_hot_records,
                  get_routing_distribution (using a temp in-memory DB)
  3. edge_node.py  — handle_event returns correct schema, alerted=True
  4. cloud_node.py — handle_event returns correct schema, alerted=False
  5. logger.py  — log_event, log_warning, log_error do not raise

Run with: pytest tests/test_execution.py -v
"""

import sys
import os
import pytest
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.execution.auth    import login, verify_token, logout
from src.execution         import storage
from src.execution.edge_node  import handle_event as edge_handle
from src.execution.cloud_node import handle_event as cloud_handle
from src.execution.logger     import log_event, log_warning, log_error


# ===========================================================================
# auth.py tests
# ===========================================================================
class TestAuth:

    def test_login_success(self):
        """Valid credentials return a non-None token string."""
        token = login("admin", "hospital123")
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_login_wrong_password_returns_none(self):
        """Wrong password must return None."""
        token = login("admin", "wrongpassword")
        assert token is None

    def test_login_unknown_user_returns_none(self):
        """Unknown username must return None."""
        token = login("hacker", "hospital123")
        assert token is None

    def test_verify_valid_token(self):
        """verify_token() must return the username for a freshly-issued token."""
        token = login("admin", "hospital123")
        assert token is not None
        username = verify_token(token)
        assert username == "admin"

    def test_verify_invalid_token_returns_none(self):
        """verify_token() must return None for a garbage token string."""
        assert verify_token("this-is-not-a-real-token") is None

    def test_verify_empty_string_returns_none(self):
        """Empty string token must return None."""
        assert verify_token("") is None

    def test_logout_invalidates_token(self):
        """After logout, verify_token() must return None for the same token."""
        token = login("admin", "hospital123")
        assert token is not None
        logout(token)
        assert verify_token(token) is None

    def test_logout_returns_true_for_active_token(self):
        """logout() must return True when the token exists."""
        token = login("admin", "hospital123")
        assert logout(token) is True

    def test_logout_returns_false_for_nonexistent_token(self):
        """logout() must return False for an unknown token."""
        assert logout("nonexistent-token-xyz") is False

    def test_multiple_logins_produce_unique_tokens(self):
        """Each login call must produce a unique token (UUID-based)."""
        tok1 = login("admin", "hospital123")
        tok2 = login("admin", "hospital123")
        assert tok1 != tok2


# ===========================================================================
# storage.py tests (use temp file DB to avoid polluting the real DB)
# ===========================================================================
@pytest.fixture
def temp_db(tmp_path):
    """Fixture: initialise a fresh SQLite DB in a temp directory."""
    db_file = str(tmp_path / "test_app.db")
    storage.init_db(db_path=db_file)
    yield db_file
    # Reset _db_path back to default after test
    storage.init_db()


class TestStorage:

    def test_init_db_creates_file(self, tmp_path):
        """init_db() must create the .db file."""
        db_file = str(tmp_path / "fresh.db")
        storage.init_db(db_path=db_file)
        assert os.path.exists(db_file), "Database file was not created by init_db()"

    def test_save_and_retrieve_hot_record(self, temp_db):
        """save_hot() followed by get_recent_hot_records() should return the saved record."""
        record = {
            "device_id":                 "ECG-101",
            "timestamp":                 "2026-09-22T10:00:00Z",
            "routing_decision":          "EDGE",
            "reason":                    "override_critical_patient",
            "predicted_latency_ms":      210.5,
            "patient_criticality_score": 9.5,
        }
        storage.save_hot(record)
        rows = storage.get_recent_hot_records(limit=10)
        assert len(rows) >= 1
        assert rows[0]["device_id"] == "ECG-101"
        assert rows[0]["routing_decision"] == "EDGE"

    def test_save_cold(self, temp_db):
        """save_cold() should complete without exceptions."""
        storage.save_cold("ECG-102", "2026-09-22T10:05:00Z",
                          {"bandwidth_mbps": 42.3, "current_latency_ms": 35.0})

    def test_get_recent_hot_records_empty(self, temp_db):
        """get_recent_hot_records() on empty DB must return an empty list."""
        rows = storage.get_recent_hot_records(limit=10)
        assert rows == []

    def test_get_routing_distribution_empty(self, temp_db):
        """get_routing_distribution() on empty DB must return an empty dict."""
        dist = storage.get_routing_distribution()
        assert dist == {}

    def test_get_routing_distribution_counts(self, temp_db):
        """Distribution counts must match the number of records saved per decision."""
        for _ in range(3):
            storage.save_hot({"device_id": "ECG-101", "timestamp": "2026-09-22T10:00:00Z",
                              "routing_decision": "EDGE", "reason": "override_critical_patient",
                              "predicted_latency_ms": 210.0, "patient_criticality_score": 9.5})
        for _ in range(2):
            storage.save_hot({"device_id": "WEARABLE-301", "timestamp": "2026-09-22T10:01:00Z",
                              "routing_decision": "CLOUD", "reason": "ahp_decision",
                              "predicted_latency_ms": 22.0, "patient_criticality_score": 1.5})
        dist = storage.get_routing_distribution()
        assert dist.get("EDGE", 0)  == 3
        assert dist.get("CLOUD", 0) == 2

    def test_get_recent_hot_records_limit(self, temp_db):
        """get_recent_hot_records(limit=N) must return at most N records."""
        for i in range(10):
            storage.save_hot({"device_id": f"DEV-{i}", "timestamp": "2026-09-22T10:00:00Z",
                              "routing_decision": "CLOUD", "reason": "ahp_decision",
                              "predicted_latency_ms": 20.0, "patient_criticality_score": 1.0})
        rows = storage.get_recent_hot_records(limit=5)
        assert len(rows) == 5

    def test_hot_record_fields(self, temp_db):
        """Retrieved hot records must contain all expected fields."""
        storage.save_hot({"device_id": "O2-201", "timestamp": "2026-09-22T11:00:00Z",
                          "routing_decision": "CLOUD", "reason": "ahp_decision",
                          "predicted_latency_ms": 30.0, "patient_criticality_score": 2.0})
        rows = storage.get_recent_hot_records(limit=1)
        row = rows[0]
        for field in ["device_id", "timestamp", "routing_decision", "reason",
                      "predicted_latency_ms", "patient_criticality_score", "stored_at"]:
            assert field in row, f"Field '{field}' missing from hot record"


# ===========================================================================
# edge_node.py tests
# ===========================================================================
class TestEdgeNode:

    @pytest.fixture(autouse=True)
    def setup_db(self, tmp_path):
        """Use a temp DB so edge tests don't touch the real DB."""
        db_file = str(tmp_path / "edge_test.db")
        storage.init_db(db_path=db_file)
        yield
        storage.init_db()

    def _make_edge_event(self, criticality=9.5):
        return {
            "device_id":                 "ECG-101",
            "routing_decision":          "EDGE",
            "reason":                    "override_critical_patient",
            "patient_criticality_score": criticality,
            "predicted_latency_ms":      210.5,
            "timestamp":                 "2026-09-22T10:15:32Z",
            "raw_payload": {
                "bandwidth_mbps":      15.2,
                "packet_loss_pct":     12.3,
                "jitter_ms":           67.0,
                "signal_strength_dbm": -74,
                "current_latency_ms":  280.0,
            },
        }

    def test_edge_returns_dict(self):
        """edge_handle() must return a dict."""
        result = edge_handle(self._make_edge_event())
        assert isinstance(result, dict)

    def test_edge_status_field(self):
        """edge_handle() status must be 'processed_at_edge'."""
        result = edge_handle(self._make_edge_event())
        assert result["status"] == "processed_at_edge"

    def test_edge_alerted_is_true(self):
        """edge_handle() alerted must always be True (SNS-like alert fired)."""
        result = edge_handle(self._make_edge_event())
        assert result["alerted"] is True

    def test_edge_device_id_echoed(self):
        """edge_handle() must echo back the device_id."""
        result = edge_handle(self._make_edge_event())
        assert result["device_id"] == "ECG-101"

    def test_edge_required_keys(self):
        """edge_handle() result must have status, device_id, alerted."""
        result = edge_handle(self._make_edge_event())
        for key in ["status", "device_id", "alerted"]:
            assert key in result, f"Key '{key}' missing from edge result"


# ===========================================================================
# cloud_node.py tests
# ===========================================================================
class TestCloudNode:

    @pytest.fixture(autouse=True)
    def setup_db(self, tmp_path):
        """Use a temp DB so cloud tests don't touch the real DB."""
        db_file = str(tmp_path / "cloud_test.db")
        storage.init_db(db_path=db_file)
        yield
        storage.init_db()

    def _make_cloud_event(self):
        return {
            "device_id":                 "WEARABLE-301",
            "routing_decision":          "CLOUD",
            "reason":                    "ahp_decision",
            "patient_criticality_score": 1.5,
            "predicted_latency_ms":      22.3,
            "timestamp":                 "2026-09-22T10:16:00Z",
            "raw_payload": {
                "bandwidth_mbps":      68.5,
                "packet_loss_pct":     0.3,
                "jitter_ms":           5.2,
                "signal_strength_dbm": -59,
                "current_latency_ms":  18.0,
            },
        }

    def test_cloud_returns_dict(self):
        """cloud_handle() must return a dict."""
        result = cloud_handle(self._make_cloud_event())
        assert isinstance(result, dict)

    def test_cloud_status_field(self):
        """cloud_handle() status must be 'processed_in_cloud'."""
        result = cloud_handle(self._make_cloud_event())
        assert result["status"] == "processed_in_cloud"

    def test_cloud_alerted_is_false(self):
        """cloud_handle() alerted must always be False (no local alert for routine data)."""
        result = cloud_handle(self._make_cloud_event())
        assert result["alerted"] is False

    def test_cloud_device_id_echoed(self):
        """cloud_handle() must echo back the device_id."""
        result = cloud_handle(self._make_cloud_event())
        assert result["device_id"] == "WEARABLE-301"

    def test_cloud_required_keys(self):
        """cloud_handle() result must have status, device_id, alerted."""
        result = cloud_handle(self._make_cloud_event())
        for key in ["status", "device_id", "alerted"]:
            assert key in result, f"Key '{key}' missing from cloud result"


# ===========================================================================
# logger.py tests
# ===========================================================================
class TestLogger:

    def test_log_event_does_not_raise(self):
        """log_event() must complete without raising any exception."""
        try:
            log_event("TEST_EVENT", {"device_id": "ECG-101", "status": "ok"})
        except Exception as exc:
            pytest.fail(f"log_event() raised an unexpected exception: {exc}")

    def test_log_warning_does_not_raise(self):
        """log_warning() must complete without raising any exception."""
        try:
            log_warning("TEST_WARNING", {"detail": "test warning"})
        except Exception as exc:
            pytest.fail(f"log_warning() raised an unexpected exception: {exc}")

    def test_log_error_does_not_raise(self):
        """log_error() must complete without raising any exception."""
        try:
            log_error("TEST_ERROR", {"detail": "test error"})
        except Exception as exc:
            pytest.fail(f"log_error() raised an unexpected exception: {exc}")

    def test_log_file_exists_after_logging(self):
        """After logging, the log file must exist on disk."""
        log_event("TEST_FILE_CHECK", {"check": True})
        assert os.path.exists(os.path.join("logs", "system.log")), \
            "logs/system.log does not exist after logging"
