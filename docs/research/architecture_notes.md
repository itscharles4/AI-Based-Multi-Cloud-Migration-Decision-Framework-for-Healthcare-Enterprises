# System Architecture & Design Notes
> BCSE355L Cloud Architecture Design — Team: Charles (24BIT0522) · Tanmay Kapoor (24BIT0079) · Rani Gupta (24BIT0543)

---

## 1. Problem Statement

Telemedicine systems produce continuous streams of IoMT (Internet of Medical Things) data — ECG readings, SpO2 levels, wearable vitals — that must be routed in real time. The challenge is:
- **Critical** data (cardiac events) must be processed *locally* at the hospital edge with near-zero latency.
- **Routine** data (background vitals monitoring) can be offloaded to the cloud for cheaper, scalable storage and analytics.
- Traditional threshold-based routers react *after* degradation occurs. We instead **predict** degradation and route proactively.

---

## 2. System Architecture (3-Layer Stack)

```
IoMT Sensors (ECG, SpO2, Wearable)
        |
  Edge Gateway (hospital LAN)
        |
  ┌─────────────────────────────────────────────┐
  │  LAYER 1 — PREDICTION (Charles 24BIT0522)   │
  │  src/prediction/                            │
  │  LSTM (64→32 units, 20-step window)         │
  │  Input:  5 telemetry features               │
  │  Output: predicted_latency_ms + risk level  │
  └─────────────────────────────────────────────┘
        |
  ┌─────────────────────────────────────────────┐
  │  LAYER 2 — DECISION (Tanmay 24BIT0079)      │
  │  src/decision/                              │
  │  AHP MCDM (3 criteria: Criticality,         │
  │            Latency, Cloud Cost)             │
  │  Hard vetoes before AHP scoring:            │
  │    1. criticality >= 9.0 → EDGE override    │
  │    2. latency >= 300ms   → EDGE veto        │
  │  Output: "EDGE" or "CLOUD" + reason         │
  └─────────────────────────────────────────────┘
        |
  ┌─────────────────────────────────────────────┐
  │  LAYER 3 — EXECUTION (Rani 24BIT0543)       │
  │  src/execution/                             │
  │  edge_node:  SNS alert + DynamoDB + S3 + CW │
  │  cloud_node: DynamoDB + S3 + CloudWatch     │
  │  auth:       Mock Cognito (SHA-256 + UUID)  │
  │  logger:     JSON-line rotating file log    │
  │  storage:    SQLite (simulates DynamoDB+S3) │
  └─────────────────────────────────────────────┘
        |
  FastAPI REST API (src/api/main.py)
  Streamlit Dashboard (dashboard/app.py)
```

---

## 3. LSTM Architecture Rationale (Charles)

| Layer | Type | Units | Notes |
|---|---|---|---|
| lstm_1 | LSTM | 64 | `return_sequences=True` — captures short-term patterns across the 20-step window |
| dropout_1 | Dropout | 0.2 | Prevents overfitting on periodic degradation patterns |
| lstm_2 | LSTM | 32 | `return_sequences=False` — compresses to a single context vector |
| dropout_2 | Dropout | 0.2 | Second regularisation stage |
| dense_relu | Dense | 16 | Non-linear bottleneck |
| output | Dense | 1 | Linear output — scalar latency regression |

- **Loss**: MSE (penalises large latency spikes more than MAE)
- **Optimiser**: Adam (lr=1e-3)
- **Callbacks**: EarlyStopping (patience=5) + ModelCheckpoint (save best)
- **Features**: bandwidth_mbps, packet_loss_pct, jitter_ms, signal_strength_dbm, current_latency_ms
- **Window size**: 20 seconds (1 reading per second)

---

## 4. AHP Decision Criteria & Weights (Tanmay)

### Pairwise Comparison Matrix

|             | Criticality | Latency | Cost |
|-------------|-------------|---------|------|
| Criticality | 1           | 3       | 5    |
| Latency     | 1/3         | 1       | 3    |
| Cost        | 1/5         | 1/3     | 1    |

### Derived Weights (eigenvector approximation)

| Criterion          | Weight | Interpretation |
|--------------------|--------|----------------|
| Patient Criticality | ~63.7% | Clinical safety dominates |
| Predicted Latency   | ~25.8% | Network health matters |
| Cloud Cost Index    | ~10.5% | Cost is the tiebreaker |

**Consistency Ratio (CR) = ~0.037 < 0.10 ✓** — matrix is acceptably consistent.

### Scoring Formula

```
EDGE score  = w_crit * norm_crit²  +  w_lat * norm_lat  +  w_cost * norm_cost
CLOUD score = w_crit * (1-norm_crit)²  +  w_lat * (1-norm_lat)  +  w_cost * (1-norm_cost)
```

**Why squared criticality?** Mid-to-high criticality (score 6-8/10) amplifies the EDGE preference, protecting serious but non-emergency patients from being routed to cloud on cost grounds alone.

---

## 5. Execution & HIPAA Security (Rani)

| Component | Local Simulation | AWS Migration Path |
|-----------|------------------|--------------------|
| auth.py | SHA-256 hashed passwords + UUID4 tokens in memory | Amazon Cognito User Pools |
| logger.py | RotatingFileHandler (JSON lines) | Amazon CloudWatch Logs (watchtower) |
| storage.py cold | SQLite cold_storage table | Amazon S3 (boto3 put_object) |
| storage.py hot | SQLite hot_storage table | Amazon DynamoDB (boto3 put_item) |
| edge_node.py | print() alert | Amazon SNS (sns.publish) |
| cloud_node.py | Direct Python call | AWS Lambda behind API Gateway |

### HIPAA Controls Implemented

- **Access control**: Hashed passwords, expiring session tokens (1-hour TTL)
- **Audit trail**: Every routing event logged as immutable JSON line with timestamp
- **Data minimisation**: PHI stays at edge during degraded network periods (EDGE override)
- **Emergency override**: Criticality ≥ 9.0 bypasses all cost optimisation — always local
- **Encryption**: (on AWS) KMS for data at rest, TLS for data in transit

---

## 6. Data Flow Walkthrough

```
POST /ingest (20-record window + criticality + cost)
  |
  1. predict_latency(window)
     -> scaled raw features -> LSTM -> inverse-transform
     -> predicted_latency_ms, risk: LOW/MEDIUM/HIGH
  |
  2. route_decision(device_id, criticality, latency, cost)
     -> check_emergency_override(criticality >= 9.0)? -> EDGE immediately
     -> latency >= 300ms? -> EDGE veto
     -> AHP scoring -> EDGE or CLOUD
  |
  3a. EDGE -> edge_node.handle_event()
       -> LOCAL ALERT (print / SNS)
       -> save_hot() [DynamoDB sim]
       -> save_cold() [S3 sim]
       -> log_event("EDGE_PROCESSED")
  |
  3b. CLOUD -> cloud_node.handle_event()
       -> save_hot() [DynamoDB sim]
       -> save_cold() [S3 sim]
       -> log_event("CLOUD_PROCESSED")
  |
  4. log_event("PIPELINE_COMPLETE")
  |
  5. Return IngestResponse JSON
```

---

## 7. AWS Migration Mapping

| Local Component | AWS Service | Key Change |
|---|---|---|
| FastAPI /ingest | API Gateway + Lambda | Replace app with `lambda_handler.py` |
| predict_service.py | Amazon SageMaker | `sm.invoke_endpoint()` |
| router.py | AWS Lambda | No code change — pure Python |
| edge_node.py | AWS IoT Greengrass | Local Lambda component |
| cloud_node.py | AWS Lambda | Standard Lambda |
| storage.py cold | Amazon S3 | `s3.put_object()` |
| storage.py hot | Amazon DynamoDB | `table.put_item()` |
| auth.py | Amazon Cognito | `cognito-idp.initiate_auth()` |
| logger.py | Amazon CloudWatch | `watchtower.CloudWatchLogHandler` |
| Streamlit dashboard | Amazon QuickSight | DynamoDB/S3 as data source |
| print() alert | Amazon SNS | `sns.publish()` |

---

## 8. Key References

1. Saaty, T.L. (1980). *The Analytic Hierarchy Process*. McGraw-Hill.
2. Hochreiter, S. & Schmidhuber, J. (1997). *Long Short-Term Memory*. Neural Computation.
3. AWS IoT Greengrass Developer Guide — aws.amazon.com/greengrass
4. HIPAA Security Rule (45 CFR Part 164) — hhs.gov/hipaa
5. AWS Well-Architected Framework — Healthcare Lens
