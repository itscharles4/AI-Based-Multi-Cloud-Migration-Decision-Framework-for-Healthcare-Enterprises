# 🎤 Project Review Speech — BCSE355L Cloud Architecture Design
## AI-Based Multi-Cloud Migration Decision Framework for Healthcare Enterprises
### Using Multi-Criteria Decision Intelligence

> **Team:** Charles ([@itscharles4](https://github.com/itscharles4) - 24BIT0522) · Tanmay Kapoor (24BIT0079) · Rani Gupta ([@grani27-m](https://github.com/grani27-m) - 24BIT0543)
> **Course:** BCSE355L — Cloud Architecture Design, VIT University
> **Repository:** [github.com/itscharles4/AI-Based-Multi-Cloud-Migration-Decision-Framework-for-Healthcare-Enterprises_Cloud_Project_2026](https://github.com/itscharles4/AI-Based-Multi-Cloud-Migration-Decision-Framework-for-Healthcare-Enterprises_Cloud_Project_2026)

---

## PART 1 — CHARLES (24BIT0522)
### *Project Overview, Architecture & Prediction Layer*
**Estimated time: ~4-5 minutes**

---

Good morning, Professor. I am Charles Jehanabad, roll number 24BIT0522.

Our project is titled **"AI-Based Multi-Cloud Migration Decision Framework for Healthcare Enterprises using Multi-Criteria Decision Intelligence"** — or in short, a **Telemedicine Workload Offloader**.

### What Problem Are We Solving?

In modern hospitals, IoMT — Internet of Medical Things — devices like ECG monitors, oxygen sensors, and wearables generate **continuous real-time data** that must be processed immediately. The fundamental challenge is: **where do you process this data?**

- If you process it at the **cloud**, you get lower cost and higher compute — but if the network degrades, a patient could be in danger before the decision reaches the doctor.
- If you process it at the **edge** — locally inside the hospital — you get instant response, but at higher cost.

Our system makes this routing decision **intelligently, in real time**, for every single telemetry reading — using a combination of LSTM neural network forecasting and the Analytic Hierarchy Process.

---

### System Architecture — End to End

Let me walk you through the complete data flow:

```
IoMT Devices (ECG-101, O2-201, WEARABLE-301...)
        |  MQTT protocol (port 1883)
        v
Mosquitto MQTT Broker  [Docker container]
        |
        v
MQTT Consumer Service  [subscribes & validates]
        |  HTTP
        v
FastAPI Backend (Production-Grade)
  +-- /auth/login  /auth/logout  /auth/refresh
  +-- /ingest      /history      /stats
  +-- /admin/users /health       /metrics
  +-- 3-Layer Pipeline:
       Step 1: LSTM Prediction    --> predicted_latency_ms
       Step 2: AHP Decision       --> EDGE or CLOUD
       Step 3: Execution + Alert  --> store + notify
        |                    |
        v                    v
     Redis               PostgreSQL 18.6 (Neon.tech, Singapore)
     Cache               9 Tables: users, devices, telemetry_readings,
     Sessions            routing_decisions, alerts, audit_log,
     Rate-limit          cold_storage, dead_letters, alembic_version
        |
        v
   MLflow Server --> Model Registry --> Versioned LSTM artifacts
        |
        v
   Prometheus --> Grafana Dashboards
        |
        v
   Streamlit Dashboard (reads ONLY from REST API)
```

---

### My Contribution — Prediction Layer

I built the complete **LSTM-based latency forecasting system** in `src/prediction/`.

#### Real Data Integration — RIPE Atlas

We didn't stop at synthetic data. We integrated with **RIPE Atlas**, the global network measurement platform run by RIPE NCC with over 10,000 probes worldwide. Using our registered API key (`38afd3a4-1857-4a40-ab8f-55a6059b802d`), we downloaded **2,830,022 real RTT measurements** — 201 megabytes of actual global network latency data. This allows our model to claim it was *trained on real traffic, not simulations* — a significantly stronger research claim.

#### LSTM Model Architecture

The core model is a **2-layer stacked LSTM regressor**:

| Layer | Type | Units | Detail |
|-------|------|-------|--------|
| lstm_1 | LSTM | 64 | `return_sequences=True` captures short-term patterns |
| dropout_1 | Dropout | 20% | Prevents overfitting |
| lstm_2 | LSTM | 32 | `return_sequences=False` final context vector |
| dropout_2 | Dropout | 20% | Second regularisation |
| dense_relu | Dense | 16 | Non-linear bottleneck |
| output | Dense | 1 | Linear — scalar latency regression |

- **Loss:** MSE — penalises large spikes, critical for degradation detection
- **Optimiser:** Adam (lr=1e-3)
- **Sequence:** Sliding window of 20 readings per device

#### Risk Classification

The prediction service outputs:
- `predicted_latency_ms` — the actual forecast
- `network_degradation_risk`: **LOW** (<75ms) / **MEDIUM** (75-150ms) / **HIGH** (>=150ms)
- Tracked in **MLflow** — experiment metrics, model registry, `champion` alias

On AWS, this maps directly to **Amazon SageMaker** — the prediction function is a drop-in replacement with `sagemaker.invoke_endpoint()`.

I now hand over to Tanmay, who will explain how this prediction drives our routing decision.

---

## PART 2 — TANMAY KAPOOR (24BIT0079)
### *Decision Engine, Security & Industry-Grade Enhancements*
**Estimated time: ~4-5 minutes**

---

Thank you Charles. I am Tanmay Kapoor, roll number 24BIT0079.

I built the **multi-criteria decision engine** in `src/decision/` and led integration of the industry-grade enhancements that set our project apart.

### The AHP Decision Engine

The Analytic Hierarchy Process — AHP — is a structured mathematical technique for multi-criteria decision making. We use it to decide: given patient criticality, predicted latency, and cloud cost — EDGE or CLOUD?

#### The Three Criteria and Weights

Pairwise comparison matrix (based on clinical priority):

```
              Criticality  Latency  Cost
Criticality [    1          3        5  ]
Latency     [   1/3         1        3  ]
Cost        [   1/5        1/3       1  ]
```

Weights via eigenvector approximation:
- **Patient Criticality: 63.7%** — clinical safety dominates
- **Network Latency: 25.8%** — network health
- **Cloud Cost: 10.5%** — cost is only a tiebreaker

**Consistency Ratio = 0.037 < 0.10** — matrix is mathematically valid.

#### Two-Layer Decision Logic

**Layer 1 — Hard Vetoes (bypass AHP entirely):**
1. `criticality >= 9.0` → force **EDGE**. Reason: `override_critical_patient`
2. `predicted_latency >= 300ms` → force **EDGE**. Reason: `network_degradation_veto`

**Layer 2 — AHP Scoring:**
```
EDGE score  = w_crit x norm_crit^2  +  w_lat x norm_lat  +  w_cost x norm_cost
CLOUD score = w_crit x (1-norm_crit)^2  +  w_lat x (1-norm_lat)  +  w_cost x (1-norm_cost)
```

The **squared criticality term** amplifies EDGE preference for scores 6-8 — protecting serious but non-emergency patients at moderate latency.

---

### Industry-Grade Enhancements

This is where our project goes significantly beyond a standard prototype. We combined our Antigravity-built codebase with a second production-hardened architecture and cherry-picked the best elements from each.

#### 1. Hash-Chained Audit Log (HIPAA-Aligned)

Every action — login, ingest, routing decision, alert — is recorded in an **append-only, cryptographically hash-chained** audit table in `backend/audit.py`.

Each row stores:
- `prev_hash` — SHA-256 of the previous row
- `hash` — SHA-256 of `(prev_hash + this row's content)`

If anyone edits or deletes **any** historical row, every subsequent hash breaks — **tampering is immediately and mathematically detectable**. This is the same principle as blockchain. Run `verify_chain()` at any time to confirm integrity.

We say **"HIPAA-aligned safeguards"** — not "HIPAA compliant" — because compliance is a legal certification, not a software property.

#### 2. Device Registry + Persistent Alerts with Deduplication

- **Device table**: auto-registers unknown IoMT devices on first reading (maps to AWS IoT Core Thing Registry)
- **Alert table**: persists every clinical alert with acknowledge workflow
- **60-second deduplication**: no second CRITICAL alert for the same device within 60 seconds — prevents alert storms

#### 3. Dead-Letter Queue

Every MQTT message that fails to process is saved in the **DeadLetter table** — topic, raw payload, error message. Nothing is silently dropped. Maps to AWS SQS Dead-Letter Queue.

#### 4. Structured Logging — structlog

We use **structlog** for JSON-line logging with `request_id` per HTTP request. On AWS, these JSON lines flow directly into **CloudWatch Logs** with zero code changes.

---

### Complete Tech Stack

| Component | Technology |
|-----------|-----------|
| API Framework | FastAPI 0.111 + Pydantic v2 |
| Database | PostgreSQL 18.6 (Neon.tech, Singapore) |
| ORM + Migrations | SQLAlchemy 2.0 + Alembic |
| Auth | JWT + bcrypt, 4 RBAC roles |
| Cache | Redis 7 (rate-limit + session + dedup) |
| IoT Ingestion | Mosquitto MQTT + paho-mqtt |
| ML Tracking | MLflow (experiment tracking + model registry) |
| Metrics | Prometheus + Grafana |
| Logging | structlog (JSON-line, request_id per request) |
| Alerts | Telegram Bot API + Gmail SMTP |
| Containerisation | Docker + Docker Compose |
| CI/CD | GitHub Actions (lint + test + docker build) |
| Load Testing | Locust (3 traffic scenarios) |
| Real Data | RIPE Atlas 2.83M readings + PhysioNet BIDMC vitals |

I hand over to Rani, who will explain the execution layer, dashboard, and deployment.

---

## PART 3 — RANI GUPTA (24BIT0543)
### *Execution Layer, Observability, Deployment & Testing*
**Estimated time: ~4-5 minutes**

---

Thank you Tanmay. I am Rani Gupta, roll number 24BIT0543.

I built the **execution layer** in `src/execution/`, the enhanced **Streamlit dashboard**, and I will explain observability, testing, and deployment.

### The Execution Layer

Once the AHP engine decides EDGE or CLOUD, execution takes over.

#### Edge Node (`src/execution/edge_node.py`)

1. **Immediate alert** — Telegram message + email to doctor on-call
2. Save to **hot storage** (DynamoDB equivalent — fast indexed queries)
3. Archive raw payload to **cold storage** (S3 equivalent)
4. Log structured `EDGE_PROCESSED` event

On AWS: step 1 = `sns.publish()`, step 2 = DynamoDB `put_item`, step 3 = S3 `put_object`. **Zero logic rewrites.**

#### Cloud Node (`src/execution/cloud_node.py`)

1. Save to hot storage
2. Archive to cold storage
3. Log `CLOUD_PROCESSED` — **no alert** for routine data

#### Alert Service — Real Integration

`backend/services/alert_service.py` integrates:
- **Telegram Bot API** — formatted HTML message to configured chat ID
- **Gmail SMTP** — HTML email with criticality, device ID, latency, reason

Both use the 60-second deduplication window and are controlled by `TELEGRAM_ENABLED` / `EMAIL_ENABLED` flags in `.env`.

---

### Production Database — Neon.tech (Live)

We run on **PostgreSQL 18.6 in AWS Singapore** via Neon.tech, with 9 tables created by Alembic migration `7880b038a2aa`:

| Table | Purpose |
|-------|---------|
| `users` | Hospital staff with bcrypt passwords + RBAC |
| `devices` | IoMT device registry (auto-registers) |
| `telemetry_readings` | Raw sensor data (TimescaleDB hypertable) |
| `routing_decisions` | Every EDGE/CLOUD decision + full pipeline state |
| `alerts` | Clinical alerts with acknowledge workflow |
| `audit_log` | Hash-chained tamper-evident trail |
| `cold_storage` | Raw payload archive (S3 equivalent) |
| `dead_letters` | Failed MQTT messages |
| `alembic_version` | Migration tracking |

---

### Testing — 99 Tests, 0 Failures

| Test File | Count | Covers |
|-----------|-------|--------|
| `test_prediction.py` | 27 | LSTM schema, risk thresholds, window validation |
| `test_execution.py` | 32 | Auth, storage, edge node, cloud node, logger |
| `test_api.py` | 20 | All endpoints, clinical scenarios, 422 errors |
| `test_decision.py` | 20 | AHP weights, CR<0.10, routing decisions |
| **Total** | **99** | **0 failures, 0 warnings** |

Critical clinical scenarios tested explicitly:
- Criticality >= 9.0 → EDGE + alert every time
- Latency >= 300ms → veto fires regardless of criticality
- Routine patient (criticality 2.0, good network) → CLOUD, no alert

---

### Observability — Prometheus Metrics

At the `/metrics` endpoint:

| Metric | What It Tracks |
|--------|----------------|
| `telemetry_total{status}` | processed / duplicate / error counts |
| `routing_decisions_total{decision,reason}` | EDGE/CLOUD by reason |
| `alerts_total{severity}` | CRITICAL / WARNING counts |
| `pipeline_seconds` | End-to-end latency histogram |
| `http_request_seconds{method,path,status}` | Per-route HTTP latency |
| `dead_letters_total` | Failed MQTT message count |

---

### Streamlit Dashboard

`dashboard/app.py` connects **only to the REST API** — never directly to DB.

Features:
- JWT-authenticated login screen
- **5 live metrics**: total events, EDGE %, CLOUD %, emergency overrides, vetoes
- **4 charts**: routing donut, latency trend (75/150/300ms threshold lines), criticality vs latency scatter, decision reasons bar chart
- **Auto-refresh** toggle (5-60 second interval)
- Recent events table colour-coded by routing decision

---

### CI/CD — GitHub Actions

Every push to `main` triggers:

```
Push to GitHub
    |
    v
Job 1: Ruff lint + format check         ~1 min
    |  passes
    v
Job 2: pytest with TimescaleDB +        ~3 min
        Redis service containers
    |  passes
    v
Job 3: Docker build check (main only)   ~2 min
        Dockerfile.api + Dockerfile.mqtt
```

---

### Load Testing — Locust

`scripts/load_test.py` runs 3 concurrent traffic scenarios:
- **Normal traffic** (10x weight) — realistic IoMT, mostly CLOUD-routed
- **Degraded network** (1x) — high latency, EDGE-routed + WARNING alert
- **Emergency patient** (1x) — criticality >= 9.0, CRITICAL alert + EDGE override

**Target SLA:** p95 latency < 200ms at 50 concurrent users, error rate < 1%.

---

### AWS Migration Path — Zero Logic Rewrites

| Current | AWS Equivalent |
|---------|----------------|
| FastAPI /ingest | API Gateway + Lambda |
| LSTM predict_service | Amazon SageMaker |
| AHP router.py | AWS Lambda (already pure function) |
| Edge node | AWS IoT Greengrass |
| Cold storage | Amazon S3 |
| Hot storage | Amazon DynamoDB |
| JWT auth | Amazon Cognito |
| structlog | CloudWatch Logs (watchtower) |
| Telegram alert | Amazon SNS |
| Streamlit | Amazon QuickSight |
| Neon.tech | Amazon RDS PostgreSQL |

---

### Conclusion

To summarise — we built a **production-grade, industry-level AI-based healthcare routing system** that:

1. **Ingests** real-time IoMT telemetry via MQTT
2. **Forecasts** network latency using a 2-layer stacked LSTM trained on **2.83 million real RIPE Atlas measurements**
3. **Decides** where to process each reading using AHP with mathematically validated weights (CR = 0.037)
4. **Executes** the decision — alerting doctors instantly for critical patients, archiving all data
5. **Protects** data with a tamper-evident **hash-chained audit trail**
6. **Observes** the full system via Prometheus, Grafana, and structured JSON logging
7. **Tests** 99 automated tests with zero failures
8. **Deploys** via GitHub Actions CI/CD to live Neon.tech production PostgreSQL

Every component maps to a named AWS service. The migration requires configuration changes only — no logic rewrites.

**Thank you, Professor. We are ready for questions.**

---

## Quick Reference Card — For Q&A

| Metric | Value |
|--------|-------|
| Real RIPE Atlas readings | **2,830,022** |
| Total automated tests | **99 passing** |
| AHP Consistency Ratio | **0.037 < 0.10** |
| AHP Weight — Criticality | **63.7%** |
| AHP Weight — Latency | **25.8%** |
| AHP Weight — Cost | **10.5%** |
| Emergency threshold | **Criticality >= 9.0 -> always EDGE** |
| Network veto threshold | **Latency >= 300ms -> always EDGE** |
| Risk levels | **LOW <75ms / MEDIUM 75-150ms / HIGH >=150ms** |
| Production DB | **PostgreSQL 18.6, Neon.tech Singapore** |
| DB tables live | **9 tables** |
| Audit chain | **SHA-256 hash per row, chained to previous** |
| Alert deduplication | **60-second window per device+severity** |
| Load test target | **p95 < 200ms at 50 concurrent users** |

### Key Files
| File | Purpose |
|------|---------|
| `backend/audit.py` | Hash-chained tamper-evident audit log |
| `src/decision/router.py` | AHP scoring + veto logic |
| `src/prediction/predict_service.py` | LSTM inference |
| `backend/services/pipeline.py` | Orchestrates all 3 layers |
| `backend/services/alert_service.py` | Telegram + Email alerts |
| `data_ingestion/ripe_atlas.py` | Real network data download |
| `.github/workflows/ci.yml` | GitHub Actions CI/CD |
| `migrations/versions/` | Alembic migration to Neon.tech |
| `scripts/load_test.py` | Locust load test |
| `dashboard/app.py` | Streamlit real-time dashboard |

---
*BCSE355L Cloud Architecture Design — VIT University, October 2026*
