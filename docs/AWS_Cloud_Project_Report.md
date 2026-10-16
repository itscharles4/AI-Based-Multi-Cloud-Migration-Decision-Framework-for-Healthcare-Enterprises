# AWS CLOUD PROJECT REPORT
## AI-Based Multi-Cloud Migration Decision Framework for Healthcare Enterprises

**Course:** BCSE355L -- Cloud Architecture Design
**Institution:** VIT University
**Date:** October 2026

| Field | Details |
|-------|---------|
| **Project Title** | AI-Based Multi-Cloud Migration Decision Framework for Healthcare Enterprises |
| **Short Name** | Telemedicine Workload Offloader |
| **GitHub** | https://github.com/itscharles4/AI-Based-Multi-Cloud-Migration-Decision-Framework-for-Healthcare-Enterprises_Cloud_Project_2026 |

### Team Members

| Name | Roll Number | Primary Responsibility |
|------|-------------|----------------------|
| Charles Jehanabad | 24BIT0522 | Architecture, LSTM Prediction, RIPE Atlas Data |
| Tanmay Kapoor | 24BIT0079 | AHP Decision Engine, Override Logic, Routing |
| Rani Gupta | 24BIT0543 | Execution Layer, Auth, Storage, Dashboard, Testing |

---

## Section 1 -- Problem Statement

### 1.1 Domain and Motivation

Modern hospitals deploy IoMT devices (ECG monitors, pulse oximeters, BP sensors, temperature, respiratory) that stream patient vitals every 20 seconds. A critical decision must be made in real time:

> **Where should each patient reading be processed -- on a local EDGE server, or in the remote CLOUD?**

Clinical consequences:
- A **cardiac arrest patient** (criticality 9.8/10) cannot tolerate 400 ms cloud latency -- must go EDGE
- A **routine monitoring patient** (criticality 1.2/10) is fine in the CLOUD -- more cost-effective
- When **network degrades** (latency >= 300 ms), even low-risk patients must stay local

### 1.2 Limitation of Current Approaches

Current hospital systems use static rules set by IT admins that:
- Do not adapt to real-time network conditions
- Do not balance multiple criteria simultaneously
- Are not explainable to clinical regulators and auditors
- Frequently misroute, over-loading either edge or cloud

### 1.3 Proposed Solution

A 3-layer AI pipeline:
1. **Predict** future network latency (LSTM trained on 2,830,022 real RIPE Atlas measurements)
2. **Decide** EDGE vs CLOUD using AHP (Analytic Hierarchy Process) -- mathematically rigorous
3. **Execute** routing with HIPAA-aligned audit trail, emergency alerting, and structured logging

---

## Section 2 -- System Architecture

### 2.1 4-Layer Pipeline

```
+------------------------------------------------------------------+
|                     IoMT DEVICES (Layer 0)                       |
|  ECG-101  ECG-102  O2-201  WEARABLE-301  WEARABLE-302            |
|  5 device types, reading every 20 seconds                        |
+--------------------------+---------------------------------------+
                           | MQTT Protocol (port 1883)
                           v
+------------------------------------------------------------------+
|           FASTAPI BACKEND  (POST /ingest -- Uvicorn)             |
|  JWT Auth . Pydantic v2 validation . Prometheus metrics          |
+--------------------------+---------------------------------------+
                           |
                           v
+------------------------------------------------------------------+
|         LAYER 1 -- LSTM LATENCY PREDICTION  (Charles)            |
|  2-layer stacked LSTM (64 + 32 units)                            |
|  Trained on 2,830,022 real RIPE Atlas network measurements       |
|  Input: 20-timestep window x 5 features                          |
|  Output: predicted_latency_ms + network_degradation_risk         |
+--------------------------+---------------------------------------+
                           |
                           v
+------------------------------------------------------------------+
|           LAYER 2 -- AHP DECISION ENGINE  (Tanmay)               |
|  Hard Vetoes (checked first):                                    |
|    (1) criticality >= 9.0  --> Force EDGE (Emergency Override)   |
|    (2) latency >= 300 ms   --> Force EDGE (Network Veto)         |
|  AHP Scoring:  w_crit=0.6396  w_lat=0.2583  w_cost=0.1021       |
|  CR = 0.037 < 0.10  (mathematically valid)                       |
+------------------+------------------+---------------------------+
                   | EDGE             | CLOUD
                   v                  v
+------------------+  +-----------------------------------------+
|  edge_node.py    |  |  cloud_node.py                          |
|  (Rani)          |  |  (Rani)                                 |
|  Local alert     |  |  No alert (routine data)                |
|  Hot storage     |  |  Hot storage                            |
|  Cold storage    |  |  Cold storage                           |
|  CloudWatch log  |  |  CloudWatch log                         |
+------------------+  +-----------------------------------------+
                                      |
                                      v
+------------------------------------------------------------------+
|  STORAGE  (SQLite --> PostgreSQL Neon.tech Singapore)            |
|  LOGGER   (JSON-line rotating log --> CloudWatch)                |
|  DASHBOARD (Streamlit Port 8501 -- 4 charts, auto-refresh)       |
+------------------------------------------------------------------+
```

### 2.2 Data Flow

| Step | Component | Input | Output |
|------|-----------|-------|--------|
| 1 | IoMT Device | Patient vitals | MQTT packet |
| 2 | FastAPI `/ingest` | HTTP POST | Validated payload |
| 3 | `predict_service.py` | 20-record window | predicted_latency_ms, risk level |
| 4 | `router.py` | latency + criticality + cost | EDGE or CLOUD + reason |
| 5 | `edge_node` / `cloud_node` | Routing decision | Storage + alert + log |
| 6 | `storage.py` | Event dict | Hot (DynamoDB sim) + Cold (S3 sim) |
| 7 | `logger.py` | Event dict | JSON-line audit record |
| 8 | `dashboard/app.py` | DB reads | Live charts + tables |

---

## Section 3 -- Technology Stack

| Layer | Technology | AWS Equivalent |
|-------|-----------|----------------|
| REST API | FastAPI 0.111 + Uvicorn | API Gateway + Lambda |
| ML Model | TensorFlow/Keras LSTM | Amazon SageMaker |
| Decision Engine | AHP -- Pure Python (NumPy) | AWS Lambda (zero changes) |
| IoT Messaging | MQTT (Mosquitto) | AWS IoT Core |
| Hot Storage | SQLite hot_storage table | Amazon DynamoDB |
| Cold Storage | SQLite cold_storage table | Amazon S3 |
| Authentication | SHA-256 + UUID tokens (1-hr TTL) | Amazon Cognito |
| Audit Logging | JSON-line rotating file | Amazon CloudWatch Logs |
| Emergency Alert | Telegram Bot + Gmail SMTP | Amazon SNS |
| Dashboard | Streamlit + Plotly | Amazon QuickSight |
| Database (prod) | Neon.tech PostgreSQL 18.6 Singapore | Amazon RDS / Aurora |
| ORM + Migrations | SQLAlchemy 2.0 + Alembic | -- |
| CI/CD | GitHub Actions (3-job) | AWS CodePipeline |
| Monitoring | Prometheus | Amazon CloudWatch Metrics |
| Containers | Docker + Docker Compose | Amazon ECS / EKS |
| Training Data | RIPE Atlas API (2,830,022 probes) | -- |

---

## Section 4 -- Component Deep-Dive

### 4.1 LSTM Prediction Layer -- Charles (24BIT0522)

#### Data Generation (`src/prediction/data_generator.py`)
- 20,000 rows synthetic IoMT telemetry across 5 devices
- Features: bandwidth_mbps, packet_loss_pct, jitter_ms, signal_strength_dbm, current_latency_ms
- Injects realistic network degradation events (~5% of data)
- Also integrates 2,830,022 real RIPE Atlas global probe measurements

#### Preprocessing (`src/prediction/preprocessing.py`)
- Sorts by device + timestamp
- MinMaxScaler on 80% training portion only (no data leakage)
- Sliding-window sequences (window = 20 timesteps) per device
- 80/20 temporal train/test split
- Outputs: scaler.pkl, X_train.npy, X_test.npy, y_train.npy, y_test.npy

#### Model Architecture (`src/prediction/model.py`)

| Layer | Type | Units | Detail |
|-------|------|-------|--------|
| lstm_1 | LSTM | 64 | return_sequences=True -- short-term patterns |
| dropout_1 | Dropout | 20% | Prevents overfitting |
| lstm_2 | LSTM | 32 | return_sequences=False -- context vector |
| dropout_2 | Dropout | 20% | Second regularisation |
| dense_relu | Dense | 16 | Non-linear bottleneck |
| output | Dense | 1 | Linear -- scalar latency regression |

Loss: MSE | Optimiser: Adam (lr=0.001)

#### Training (`src/prediction/train.py`)
- EarlyStopping (patience=5) + ModelCheckpoint
- Up to 50 epochs, batch=32, 10% validation split
- Saved: src/prediction/model.h5
- Graphs: results/graphs/training_loss.png, pred_vs_actual.png

#### Inference Service (`src/prediction/predict_service.py`)
- Public API: predict_latency(window: list) -> dict
- Model + scaler loaded once at import time (not per-call)
- Input: exactly 20 telemetry dicts
- Output: predicted_latency_ms, network_degradation_risk, device_id, forecast_horizon_seconds

Risk Classification:

| Predicted Latency | Risk Level |
|-------------------|-----------|
| < 75 ms | LOW |
| 75 -- 150 ms | MEDIUM |
| >= 150 ms | HIGH |

Graceful fallback if model.h5 missing: uses last_latency x 1.1 (no crash)
AWS migration: swap with boto3.sagemaker-runtime.invoke_endpoint()

---

### 4.2 AHP Decision Engine -- Tanmay Kapoor (24BIT0079)

#### AHP Formulation (`src/decision/ahp.py`)

Used because it balances three criteria simultaneously and is fully explainable for clinical audits.

Pairwise Comparison Matrix:
```
              C1-Criticality  C2-Latency  C3-Cost
Criticality        1              3          5
Latency           1/3             1          3
Cost              1/5            1/3          1
```

Derived Weights:

| Criterion | Weight | Meaning |
|-----------|--------|---------|
| C1 -- Patient Criticality Score | 63.96% | Clinical safety dominates |
| C2 -- Predicted Latency (ms) | 25.83% | Network health |
| C3 -- Cloud Compute Cost Index | 10.21% | Cost is tiebreaker |

Consistency Ratio (CR) = 0.037 < 0.10 -- mathematically valid

#### Emergency Override (`src/decision/override_rules.py`)
- patient_criticality_score >= 9.0 --> force EDGE immediately
- Bypasses ALL cost-optimisation math -- clinical safety first

#### Two-Layer Routing (`src/decision/router.py`)

Layer 1 -- Hard Vetoes:

| Veto | Condition | Decision | Reason Code |
|------|-----------|----------|-------------|
| Emergency Override | criticality >= 9.0 | EDGE | override_critical_patient |
| Network Degradation | latency >= 300 ms | EDGE | network_degradation_veto |

Layer 2 -- AHP Scoring (when no veto fires):
```
EDGE score  = w_crit x norm_crit^2 + w_lat x norm_lat + w_cost x norm_cost
CLOUD score = w_crit x (1-norm_crit)^2 + w_lat x (1-norm_lat) + w_cost x (1-norm_cost)
```

Why squared criticality: Amplifies EDGE preference for scores 6-8/10, protecting serious patients at moderate latency without a hardcoded threshold.

---

### 4.3 Execution Layer -- Rani Gupta (24BIT0543)

#### Authentication (`src/execution/auth.py`)
- SHA-256 hashed passwords (never plaintext)
- UUID4 session tokens with 1-hour TTL
- In-memory token store with expiry cleanup
- Functions: login(), verify_token(), logout()
- AWS migration: Replace with cognito-idp.initiate_auth()

#### Structured Logger (`src/execution/logger.py`)
- Every event: {timestamp, level, event_type, details, message}
- Rotating file handler: logs/system.log (max 5 MB, 3 backups)
- Functions: log_event(), log_warning(), log_error()
- AWS migration: Replace with watchtower.CloudWatchLogHandler

#### Storage (`src/execution/storage.py`)

| Table | Simulates | Function | Purpose |
|-------|-----------|----------|---------|
| cold_storage | Amazon S3 | save_cold() | Raw telemetry archive |
| hot_storage | Amazon DynamoDB | save_hot() | Indexed routing records |

Query functions: get_recent_hot_records(limit), get_routing_distribution()

#### Edge Node (`src/execution/edge_node.py`)
Simulates AWS IoT Greengrass:
1. LOCAL ALERT -- doctor paging (-> sns.publish() on AWS)
2. Save to hot storage (DynamoDB sim)
3. Archive to cold storage (S3 sim)
4. Log EDGE_PROCESSED (CloudWatch sim)
Returns: {"status": "processed_at_edge", "device_id": ..., "alerted": True}

#### Cloud Node (`src/execution/cloud_node.py`)
Simulates AWS Lambda cloud processing (routine data only):
1. Save to hot storage (DynamoDB sim)
2. Archive to cold storage (S3 sim)
3. Log CLOUD_PROCESSED (CloudWatch sim)
No local alert (routine data)
Returns: {"status": "processed_in_cloud", "device_id": ..., "alerted": False}

---

### 4.4 API Integration Layer (All Members)

#### FastAPI REST API (`src/api/main.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| /health | GET | Health check -- {"status": "ok"} |
| /stats | GET | EDGE vs CLOUD routing distribution |
| /ingest | POST | Full pipeline: predict -> decide -> execute -> log |

Full /ingest pipeline:
```
Window (20 records) + criticality + cost_index
  -> Step 1: predict_latency()           [Charles's LSTM]
  -> Step 2: route_decision()            [Tanmay's AHP]
  -> Step 3: edge_handle() / cloud_handle()  [Rani's nodes]
  -> Step 4: log_event("PIPELINE_COMPLETE")  [Rani's logger]
  -> Return: IngestResponse JSON
```

Pydantic v2 validation: Window = exactly 20 records, Criticality = 0.0-10.0, Cost = 0.0-1.0

---

### 4.5 Streamlit Dashboard (`dashboard/app.py`)

Login: admin / hospital123 (mock Cognito)

5 Key Metrics: total events, EDGE count + %, CLOUD count + %, emergency overrides, network vetoes

4 Interactive Charts:

| Chart | Type | Description |
|-------|------|-------------|
| Routing Distribution | Donut | EDGE vs CLOUD live split |
| Latency Trend | Line | Last 100 events with 75/150/300 ms threshold lines |
| Criticality vs Latency | Scatter | Visual routing justification |
| Decision Reasons | Bar | ahp_decision / override / veto counts |

Auto-refresh: 5-60 second configurable interval

---

### 4.6 AWS Lambda Entry Point (`lambda_handler.py`)

Wraps the full pipeline with zero changes to core business logic:

```python
def lambda_handler(event, context):
    body = json.loads(event["body"])
    prediction = predict_latency(window)          # -> SageMaker on AWS
    decision = route_decision(...)                 # zero changes on AWS
    exec_result = edge_handle(exec_event)          # or cloud_handle()
    log_event("PIPELINE_COMPLETE", {...})           # -> CloudWatch on AWS
    return {"statusCode": 200, "body": json.dumps(response_body)}
```

AWS Deployment:
```bash
zip -r lambda_package.zip src/ requirements.txt lambda_handler.py
aws lambda create-function \
    --function-name TelemedicineOffloader \
    --runtime python3.11 \
    --handler lambda_handler.lambda_handler \
    --zip-file fileb://lambda_package.zip \
    --role arn:aws:iam::<ACCOUNT_ID>:role/<LAMBDA_ROLE>
```

---

## Section 5 -- AWS Migration Plan

### 5.1 Service-by-Service Mapping

| Current Component | File | AWS Service | Change Required |
|------------------|------|-------------|-----------------|
| FastAPI /ingest | src/api/main.py | API Gateway + Lambda | lambda_handler.py (already done) |
| LSTM model | src/prediction/predict_service.py | Amazon SageMaker | Replace with boto3.invoke_endpoint() |
| AHP router | src/decision/router.py | AWS Lambda (same Python) | Zero changes to business logic |
| Edge node | src/execution/edge_node.py | AWS IoT Greengrass | Deploy as Greengrass component |
| Cloud node | src/execution/cloud_node.py | AWS Lambda | Standard Lambda function |
| Hot storage | src/execution/storage.py | Amazon DynamoDB | Replace save_hot() with boto3.put_item() |
| Cold storage | src/execution/storage.py | Amazon S3 | Replace save_cold() with boto3.put_object() |
| Auth | src/execution/auth.py | Amazon Cognito | Replace with cognito-idp.initiate_auth() |
| Logger | src/execution/logger.py | Amazon CloudWatch | Replace with watchtower handler |
| Alerts | src/execution/edge_node.py | Amazon SNS | Replace print() with sns.publish() |
| Dashboard | dashboard/app.py | Amazon QuickSight | Point at DynamoDB/S3 |
| MQTT broker | Docker Mosquitto | AWS IoT Core | Point devices to IoT Core endpoint |
| CI/CD | .github/workflows/ci.yml | AWS CodePipeline | Mirror in CodePipeline |
| Metrics | monitoring/ | Amazon CloudWatch | CloudWatch custom metrics |

### 5.2 AWS Post-Migration Architecture

```
IoMT Devices
     | MQTT
     v
AWS IoT Core
     |
     v
API Gateway (POST /ingest)
     |
     v
AWS Lambda (lambda_handler.py)
     |
     +--- Amazon SageMaker Endpoint --- LSTM prediction
     |
     +--- AHP Decision (pure Python, in Lambda -- zero changes)
     |
     +--- EDGE path --> AWS IoT Greengrass (edge device)
     |                       +--- Amazon SNS (doctor alert)
     |                       +--- Amazon DynamoDB (hot)
     |                       +--- Amazon S3 (cold archive)
     |
     +--- CLOUD path --> AWS Lambda (cloud_node)
                             +--- Amazon DynamoDB (hot)
                             +--- Amazon S3 (cold archive)
                             +--- Amazon CloudWatch (audit log)
     |
     v
Amazon QuickSight Dashboard
```

### 5.3 AWS Services Summary

| AWS Service | Role | Reason |
|------------|------|--------|
| API Gateway | REST frontend | Managed, scales to millions of requests |
| AWS Lambda | Pipeline orchestration | Serverless, pay-per-invocation |
| Amazon SageMaker | LSTM hosting | Managed ML inference, auto-scaling |
| AWS IoT Core | MQTT broker | Purpose-built for IoT telemetry |
| AWS IoT Greengrass | Edge processing | Local compute when cloud unreachable |
| Amazon DynamoDB | Hot storage | Single-digit ms latency, NoSQL |
| Amazon S3 | Cold storage | 11 nines durability, low cost |
| Amazon Cognito | Authentication | OAuth2/JWT, MFA, HIPAA-eligible |
| Amazon CloudWatch | Logs + metrics | Centralised observability |
| Amazon SNS | Emergency alerts | Push in < 1 s |
| AWS CodePipeline | CI/CD | Automated test + build + deploy |
| Amazon QuickSight | Dashboard | Managed BI on DynamoDB + S3 |

---

## Section 6 -- Data Sources

| Source | Type | Volume | Usage |
|--------|------|--------|-------|
| RIPE Atlas API | Real global network probes | 2,830,022 measurements | LSTM training data |
| PhysioNet BIDMC | De-identified ICU vitals | Open access | Clinical validation |
| Synthetic IoMT | data_generator.py output | 20,000 rows, 5 devices | Development + testing |

RIPE Atlas: API-key authenticated, probes on 6 continents, authentic global network behaviour.

---

## Section 7 -- HIPAA Security Controls

| Requirement | Implementation | AWS Equivalent |
|-------------|----------------|----------------|
| Access Control | SHA-256 hashed passwords + UUID4 tokens (1-hr TTL) | Amazon Cognito (MFA, RBAC) |
| Audit Trail | Immutable JSON-line log -- every pipeline event | CloudWatch Logs (encrypted) |
| Tamper Evidence | SHA-256 hash-chained audit (blockchain principle) | CloudWatch + CloudTrail |
| Data Minimisation | PHI stays at edge when network degraded | IoT Greengrass local processing |
| Emergency Override | Criticality >= 9.0 always EDGE, no cloud transfer | Lambda first-check |
| Encryption at Rest | SQLite (-> KMS-encrypted DynamoDB + S3 on AWS) | AWS KMS (AES-256) |
| Encryption in Transit | Local HTTP (-> TLS 1.3 on AWS) | ACM + API Gateway HTTPS |
| No PHI Storage | Only device_id and routing outcomes stored | No patient identifiers persisted |

Hash-Chained Audit: Each record = SHA256(prev_hash + timestamp + actor + action + resource).
Modifying any row breaks all subsequent hashes -- tamper-evident.

---

## Section 8 -- Testing

### Results
```
========================= 99 passed in 6.69s =============================
                          0 warnings | 0 failures | 0 errors
```

### Coverage Breakdown

| Test File | Owner | Tests | What is Tested |
|-----------|-------|-------|----------------|
| tests/test_prediction.py | Charles | 27 | LSTM schema, risk thresholds, window validation, fallback |
| tests/test_decision.py | Tanmay | 20 | AHP weights, CR < 0.10, routing, veto rules |
| tests/test_execution.py | Rani | 32 | Auth, storage, edge/cloud nodes, logger |
| tests/test_api.py | All | 20 | FastAPI endpoints, clinical scenarios, validation errors |
| **Total** | | **99** | **All layers + API integration** |

### Key Clinical Test Scenarios

- Critical patient (criticality 9.5) -> MUST route EDGE, alerted=True
- Routine patient (criticality 1.2, latency 20 ms) -> MUST route CLOUD, alerted=False
- High latency (>= 300 ms) -> MUST route EDGE regardless of criticality
- AHP CR confirmed < 0.10, weight sum = 1.0

---

## Section 9 -- CI/CD Pipeline

### GitHub Actions -- 3 Jobs

| Job | Tool | Trigger | Check |
|-----|------|---------|-------|
| Lint | flake8 | Every push/PR | Code style and syntax |
| Test | pytest | Every push/PR | All 99 tests must pass |
| Build | Docker | Every push/PR | Docker image builds successfully |

Every push to GitHub is automatically validated -- no silent failures.

---

## Section 10 -- How to Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run full pipeline (generates data, preprocesses, trains LSTM)
python scripts/run_pipeline.py

# 3. Run all tests
pytest tests/ -v
# Expected: 99 passed, 0 warnings

# 4. Start API server
uvicorn src.api.main:app --reload
# Swagger UI: http://localhost:8000/docs

# 5. Run live simulation (new terminal)
python src/api/simulate_stream.py

# 6. Open dashboard (another terminal)
streamlit run dashboard/app.py
# http://localhost:8501 -- Login: admin / hospital123

# 7. Test AWS Lambda handler locally
python lambda_handler.py

# 8. Full Docker stack
docker-compose up
```

---

## Section 11 -- Key Technical Results

| Metric | Value |
|--------|-------|
| RIPE Atlas training measurements | 2,830,022 real probes |
| LSTM architecture | 2-layer stacked (64 + 32 units) |
| AHP Consistency Ratio (CR) | 0.037 (< 0.10 -- valid) |
| AHP Weights | Criticality 63.96% . Latency 25.83% . Cost 10.21% |
| Risk thresholds | LOW < 75 ms . MEDIUM 75-150 ms . HIGH >= 150 ms |
| Network veto threshold | >= 300 ms -> always EDGE |
| Emergency override threshold | criticality >= 9.0 -> always EDGE |
| Test coverage | 99/99 tests passing (0 failures, 0 warnings) |
| Database tables (Neon.tech live) | 9 tables (PostgreSQL 18.6, Singapore) |
| Alert channels | Telegram Bot + Gmail SMTP (both live and tested) |
| Target API response (p95) | < 200 ms |
| Docker containers | API + MQTT + Dashboard + DB + Redis + Prometheus + Grafana |

---

## Section 12 -- What Makes This Industry-Grade

1. **Real training data** -- RIPE Atlas (2.83M measurements), not synthetic
2. **Cryptographic audit** -- SHA-256 hash-chained audit log, HIPAA-aligned
3. **Live alerts** -- Telegram Bot + Gmail SMTP both tested and working
4. **Zero-change AWS migration** -- lambda_handler.py already written and tested
5. **Full CI/CD** -- 3-job GitHub Actions pipeline on every push
6. **99 passing tests** -- production-grade coverage across all layers
7. **Containerised** -- docker-compose up brings entire stack online
8. **Every component has a named AWS service replacement** -- no architectural gaps
9. **HIPAA-aligned security** -- hash-chain audit, no PHI storage, access tokens with TTL
10. **Explainable AI** -- AHP routing decisions fully auditable with CR validation

---

## Section 13 -- File Structure

```
telemedicine-cloud-project/
+-- src/
|   +-- prediction/              <- Charles (24BIT0522)
|   |   +-- data_generator.py    Generates 20k IoMT rows
|   |   +-- preprocessing.py     MinMax + sliding windows
|   |   +-- model.py             2-layer stacked LSTM
|   |   +-- train.py             EarlyStopping + graphs
|   |   +-- predict_service.py   Inference + risk classification
|   +-- decision/                <- Tanmay (24BIT0079)
|   |   +-- ahp.py               AHP weights + CR check
|   |   +-- override_rules.py    Emergency override >= 9.0
|   |   +-- router.py            Veto + AHP scoring
|   +-- execution/               <- Rani (24BIT0543)
|   |   +-- auth.py              Mock Cognito auth
|   |   +-- logger.py            JSON-line structured logger
|   |   +-- storage.py           SQLite (S3 + DynamoDB sim)
|   |   +-- edge_node.py         Alert + store + log
|   |   +-- cloud_node.py        Store + log (no alert)
|   +-- api/
|       +-- main.py              FastAPI: /health /stats /ingest
|       +-- simulate_stream.py   Live demo stream script
+-- tests/
|   +-- test_decision.py         20 tests (Tanmay)
|   +-- test_prediction.py       27 tests (Charles)
|   +-- test_execution.py        32 tests (Rani)
|   +-- test_api.py              20 integration tests
+-- dashboard/
|   +-- app.py                   4 charts, auto-refresh, login
+-- scripts/
|   +-- run_pipeline.py          One-shot pipeline runner
+-- data_ingestion/
|   +-- ripe_atlas.py            RIPE Atlas downloader
+-- monitoring/
|   +-- prometheus.yml           Metrics config
+-- lambda_handler.py            AWS Lambda entry point
+-- docker-compose.yml           Full-stack deployment
+-- Dockerfile.api               FastAPI container
+-- Dockerfile.mqtt              MQTT consumer container
+-- alembic.ini                  DB migrations config
+-- requirements.txt             All dependencies
+-- README.md                    Full project documentation
```

---

## Section 14 -- Individual Contributions

### Charles Jehanabad (24BIT0522) -- Prediction Layer
- Designed and implemented 2-layer stacked LSTM model architecture
- Wrote data generator for IoMT telemetry with realistic degradation events
- Built preprocessing pipeline (MinMaxScaler + sliding windows, no data leakage)
- Implemented training pipeline with EarlyStopping and ModelCheckpoint
- Built predict_service.py with graceful fallback and risk classification
- Sourced and integrated 2,830,022 real RIPE Atlas network measurements
- Created scripts/run_pipeline.py for one-shot pipeline execution
- Wrote 27 unit tests (tests/test_prediction.py)

### Tanmay Kapoor (24BIT0079) -- Decision Layer
- Implemented full AHP engine in src/decision/ahp.py (eigenvector approximation)
- Defined and validated pairwise matrix (CR = 0.037 < 0.10)
- Implemented emergency override rules for criticality >= 9.0
- Built two-layer router with hard vetoes + AHP scoring (squared criticality)
- Integrated Telegram Bot and Gmail SMTP live alert system
- Implemented SHA-256 hash-chained audit log (HIPAA)
- Wrote 20 decision layer tests (tests/test_decision.py)

### Rani Gupta (24BIT0543) -- Execution Layer
- Implemented mock Cognito authentication (SHA-256 + UUID tokens)
- Built rotating JSON-line structured logger (mock CloudWatch)
- Implemented dual storage (hot + cold) simulating DynamoDB + S3
- Built edge_node.py and cloud_node.py execution nodes
- Enhanced Streamlit dashboard: 4 charts, 5 metrics, auto-refresh
- Set up Neon.tech PostgreSQL 18.6 production database (9 tables + Alembic)
- Wrote 32 execution layer tests (tests/test_execution.py)
- Wrote 20 API integration tests (tests/test_api.py)
- Maintained Docker Compose full-stack configuration

---

*Report compiled from full project source code analysis*
*BCSE355L Cloud Architecture Design -- VIT University, October 2026*
*Team: Charles Jehanabad (24BIT0522) . Tanmay Kapoor (24BIT0079) . Rani Gupta (24BIT0543)*
