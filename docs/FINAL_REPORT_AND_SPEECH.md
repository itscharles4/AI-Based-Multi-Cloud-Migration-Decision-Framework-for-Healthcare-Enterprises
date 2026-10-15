# AI-Based Multi-Cloud Migration Decision Framework for Healthcare Enterprises
## BCSE355L - Cloud Architecture Design | VIT University | October 2026

---

# PART A -- DETAILED PROJECT REPORT

---

## 1. Project Title and Team

**Full Title:** AI-Based Multi-Cloud Migration Decision Framework for Healthcare Enterprises using Multi-Criteria Decision Intelligence

**Short Name:** Telemedicine Workload Offloader

| Member | Roll No | Primary Role |
|--------|---------|--------------|
| Charles Jehanabad | 24BIT0522 | Architecture, LSTM Prediction, RIPE Atlas Data |
| Tanmay | 24BIT0537 | AHP Decision Engine, Override Logic, Alerts |
| [Third Member] | 24BIT0543 | Database, Testing, CI/CD, Dashboard |

**GitHub:** https://github.com/itscharles4/AI-Based-Multi-Cloud-Migration-Decision-Framework-for-Healthcare-Enterprises

---

## 2. Problem Statement

Modern hospitals use Internet of Medical Things (IoMT) devices -- ECG monitors, pulse oximeters, blood pressure sensors, ventilators -- that continuously stream patient vital signs every 20 seconds.

The core problem:
> **Where should each patient reading be processed -- on a local EDGE server, or in the remote CLOUD?**

- A cardiac arrest patient (criticality = 9.8/10) cannot tolerate 400ms cloud latency -- must go EDGE.
- A routine check patient (criticality = 1.2/10) is perfectly fine in the CLOUD -- more cost-effective.
- When the network degrades (packet loss 14%, latency 300ms+), even low-risk data must stay local.

Current hospital systems use static rules set by IT admins. **Our project automates this with AI.**

---

## 3. System Architecture (4-Layer Pipeline)

`
IoMT Sensors (ECG-101, SPO2-202, BP-303, TEMP-404, RESP-505)
    |
    | MQTT Protocol (Mosquitto Broker)
    v
FastAPI Backend (Uvicorn / Port 8000)
    - POST /ingest: validates payload, triggers pipeline
    - JWT Authentication (bcrypt hashed)
    - Prometheus metrics at /metrics
    |
    v
LAYER 1 -- LSTM PREDICTION
    - 2-layer stacked LSTM (64 + 32 units)
    - Trained on 2,830,022 real RIPE Atlas measurements
    - Window: 20 timesteps | Features: 5
    - Output: predicted_latency_ms
    |
    v
LAYER 2 -- AHP DECISION ENGINE
    Hard Vetoes (checked first):
      (1) criticality >= 9.0  --> Force EDGE (Emergency Override)
      (2) latency >= 300ms    --> Force EDGE (Network Veto)
    AHP Scoring (when no veto fires):
      Weights: w_crit=0.6396, w_lat=0.2583, w_cost=0.1021
      CR = 0.037 < 0.10 (mathematically valid)
    |
    |-- EDGE -----------------> edge_node.py
    |                             - Saves to hot_records table
    |                             - Fires Telegram + Email alert
    |-- CLOUD ----------------> cloud_node.py
                                  - Saves to routing_decisions table
                                  - Archives to cold_storage
    |
    v
NEON.TECH POSTGRESQL 18.6 (Singapore)
    - 9 live tables
    - SHA-256 hash-chained audit log (HIPAA-aligned)
    |
    v
STREAMLIT DASHBOARD (Port 8501)
    - Login (admin / hospital123)
    - EDGE vs CLOUD donut chart
    - Latency trend chart
    - Criticality scatter plot
    - Metrics row + events table
    - Auto-refresh
`

---

## 4. Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| API | FastAPI + Uvicorn | REST API, async handling |
| ML Model | LSTM (TensorFlow/Keras) | Latency prediction |
| Decision Engine | AHP (Pure Python) | Edge vs Cloud routing |
| Database | Neon.tech PostgreSQL 18.6 | Cloud-hosted persistence |
| ORM + Migrations | SQLAlchemy 2.0 + Alembic | DB models and schema |
| Messaging | MQTT (Mosquitto) | IoMT device telemetry |
| Mobile Alert | Telegram Bot API | Emergency push alert |
| Email Alert | Gmail SMTP | Emergency email alert |
| Dashboard | Streamlit + Plotly | Real-time web portal |
| Auth | JWT + bcrypt | Secure login |
| CI/CD | GitHub Actions (3 jobs) | Automated test pipeline |
| Monitoring | Prometheus | Metric collection |
| Audit | SHA-256 hash chain | HIPAA tamper log |
| Containers | Docker + Docker Compose | Full-stack deployment |
| AWS Target | Lambda, SageMaker, IoT Core, DynamoDB, S3, SNS | Production migration |
| Training Data | RIPE Atlas API | 2,830,022 real network probes |

---

## 5. Component Deep-Dive

### 5.1 LSTM Latency Forecasting Model
- Architecture: 2-layer stacked LSTM
  - Layer 1: 64 LSTM units (returns sequences)
  - Layer 2: 32 LSTM units (returns single vector)
  - Dense: 1 output neuron (predicted latency ms)
- Training: 2,830,022 real RIPE Atlas measurements
- Input: 5 features per step (bandwidth, packet_loss, jitter, signal_strength, current_latency)
- Window: 20 timesteps (~6.7 minutes of history)
- Risk levels: LOW (<75ms) | MEDIUM (75-150ms) | HIGH (>=150ms)
- AWS Migration: swap model.h5 with boto3.invoke_endpoint() to SageMaker

### 5.2 AHP Decision Engine
- 3 criteria: Patient Criticality (64%), Network Latency (26%), Cloud Cost (10%)
- CR = 0.037 -- validated below 0.10 threshold
- Layer 1 vetoes override all AHP math:
  - Emergency: criticality >= 9.0 --> EDGE (no math, safety first)
  - Network: latency >= 300ms --> EDGE (cloud path unreliable)
- Layer 2: AHP scoring, higher score wins

### 5.3 Alert System (LIVE AND TESTED)
- Telegram: @TelemedicineCAD_bot --> chat ID 5243964646
- Email: charlesjehanabad12345@gmail.com via Gmail App Password
- Both fire simultaneously on every emergency EDGE override
- Non-blocking: async executor, never delays API

### 5.4 HIPAA Audit Log
- SHA-256 hash-chained: each row = SHA256(prev_hash + ts + actor + action + resource)
- Tamper-evident: modify any row --> all subsequent hashes break
- No PHI stored: only device IDs and routing outcomes

### 5.5 Database (9 Tables on Neon.tech)
| Table | Purpose |
|-------|---------|
| users | JWT auth accounts |
| telemetry_readings | Raw IoMT sensor data |
| routing_decisions | Every EDGE/CLOUD decision + scores |
| hot_records | Emergency EDGE events (fast access) |
| cold_storage | Archived routine cloud data |
| audit_log | Hash-chained tamper-evident log |
| alembic_version | DB migration state tracker |

### 5.6 AWS Migration Path
| Current | AWS Production |
|---------|---------------|
| FastAPI | API Gateway + Lambda |
| LSTM model.h5 | SageMaker Hosted Endpoint |
| PostgreSQL (Neon) | DynamoDB (hot) + S3 (cold) |
| Telegram alert | SNS (Simple Notification Service) |
| Mosquitto MQTT | AWS IoT Core |
| GitHub Actions | AWS CodePipeline |
| Prometheus | AWS CloudWatch |
| Streamlit | AWS QuickSight |

### 5.7 CI/CD Pipeline (GitHub Actions, 3 jobs)
1. Lint -- flake8 code quality
2. Test -- all 99 pytest tests
3. Build -- Docker image validation

---

## 6. Data Sources

- RIPE Atlas: 2,830,022 real network measurements (global probes, API key authenticated)
- PhysioNet BIDMC: de-identified ICU vitals (open access, wfdb library, no key needed)
- Simulated IoMT: 20,000 synthetic readings (simulate_stream.py), 5 device types

---

## 7. Results

| Metric | Value |
|--------|-------|
| RIPE Atlas measurements | 2,830,022 |
| Tests passed | 99 / 99 (0 failures) |
| DB tables (live) | 9 (Neon.tech) |
| AHP Consistency Ratio | 0.037 |
| Emergency threshold | >= 9.0/10 |
| Network veto threshold | >= 300ms |
| Alert channels | Telegram + Email (BOTH LIVE) |
| Target p95 response | < 200ms |
| DB region | Singapore (ap-southeast-1) |

---

## 8. What Makes This Industry-Grade

1. Real training data -- RIPE Atlas, not synthetic
2. Cryptographic audit -- SHA-256 hash chain, HIPAA-aligned
3. Live alerts -- Telegram + Email both tested and working
4. Zero-change AWS migration -- lambda_handler.py already written
5. Full CI/CD -- 3-job GitHub Actions on every push
6. 99 passing tests -- production-grade coverage
7. Containerised -- docker-compose up brings entire stack
8. Every component has a named AWS service replacement


---
---

# PART B -- VIVA SPEECH SCRIPT (3 Members, ~15 minutes)

---

## CHARLES (24BIT0522) -- ~5 minutes
## Topic: Problem Statement, Architecture, LSTM, RIPE Atlas

Good morning, Professor. I am Charles Jehanabad, roll number 24BIT0522.

Our project is titled AI-Based Multi-Cloud Migration Decision Framework for Healthcare Enterprises using Multi-Criteria Decision Intelligence -- or simply, a Telemedicine Workload Offloader.

### The Problem

Professor, imagine a hospital ICU. There are 5 types of IoMT medical devices running simultaneously -- ECG machines, pulse oximeters, blood pressure monitors, temperature sensors, and respiratory monitors. Every 20 seconds, each device sends a packet of patient vitals.

The critical question is: Where should this data be processed?

On a local EDGE server -- fast, but expensive and limited in capacity.
On the remote CLOUD -- scalable, but adds 50 to 400 milliseconds of network latency.

For a patient having a cardiac arrest, criticality score 9.8 out of 10, even 200 milliseconds can cost a life. That patient must go to EDGE.

But for a routine check patient, criticality 1.2, cloud processing is perfectly fine and more cost-effective.

Currently hospitals use static rules set by IT administrators. These do not adapt to real-time network conditions. Our project automates this routing decision intelligently using AI.

### System Architecture

Our system has a 4-layer pipeline.

Layer 0: Data Ingestion. IoMT devices send readings via MQTT protocol to a Mosquitto broker. Our FastAPI backend receives these at the /ingest endpoint with JWT authentication.

Layer 1: LSTM Prediction. Before any routing decision, we predict what network latency will be next. This is our AI model -- a 2-layer stacked LSTM. Layer 1 has 64 units, Layer 2 has 32 units, using a sliding window of 20 timesteps with 5 features per step.

Layer 2: AHP Decision Engine -- I will hand over to Tanmay.
Layer 3: Execution and Storage -- to our third member.

### RIPE Atlas Data

I want to highlight our training data specifically. We did not use synthetic network data. We registered on RIPE Atlas, obtained an API key, and downloaded 2,830,022 real latency measurements from probes spanning 6 continents. Our LSTM is trained on authentic global network behaviour.

I now hand over to Tanmay.

---

## TANMAY (24BIT0537) -- ~5 minutes
## Topic: AHP Engine, Override Rules, Alert System, HIPAA

Thank you Charles. Good morning Professor. I am Tanmay, roll number 24BIT0537.

### The AHP Decision Engine

Once the LSTM gives us the predicted latency, the routing decision is made by our Analytic Hierarchy Process engine -- a mathematically rigorous multi-criteria decision method from operations research.

We have 3 decision criteria:
- Patient Criticality: weight 0.6396 -- that is 64 percent
- Network Latency: weight 0.2583 -- that is 26 percent
- Cloud Cost Index: weight 0.1021 -- that is 10 percent

Our Consistency Ratio is 0.037 -- well below the accepted threshold of 0.10. This means the weights are mathematically valid.

### Two-Layer Decision Logic

We do not blindly apply AHP. There are two layers.

Layer 1: Hard Vetoes -- checked first, before any scoring:

First, Emergency Override: if patient criticality is 9.0 or above, the system immediately forces EDGE -- no math, no overriding. Clinical safety takes absolute priority.

Second, Network Degradation Veto: if the LSTM predicts latency of 300ms or above, the cloud path is declared unreliable. Even low-risk patients route to EDGE during severe network degradation.

Layer 2: AHP Scoring -- only when neither veto fires. We calculate EDGE score and CLOUD score using weighted normalised criteria. Whichever is higher, that is the routing decision.

### Alert System

When an emergency routing occurs, criticality above 9.0, our system fires two simultaneous real-time alerts.

One: Telegram Bot -- @TelemedicineCAD_bot. A formatted push message reaches the on-call doctor's phone within 2 to 3 seconds. We demonstrated this today -- it works.

Two: Gmail SMTP Email. A rich HTML alert email with patient device ID, criticality score, predicted latency, and reason. This also works live.

Both alerts fire asynchronously -- they do not delay the API response. The system continues processing immediately.

### HIPAA Compliance

Professor, in healthcare every decision must be auditable. We implemented a SHA-256 hash-chained audit log -- the same principle as blockchain.

Every routing decision stores: SHA-256 of previous hash, plus timestamp, plus actor, plus action, plus resource.

If anyone modifies or deletes even one historical record, every subsequent hash breaks. This gives us a tamper-evident, append-only audit trail aligned with HIPAA requirements. No Protected Health Information is stored -- only device IDs and routing outcomes.

I now hand over to our third member.

---

## [THIRD MEMBER] (24BIT0543) -- ~5 minutes
## Topic: Database, Dashboard, Testing, CI/CD, AWS Migration

Thank you Tanmay. Good morning Professor. I am [name], roll number 24BIT0543.

### Database

All data is persisted in a live cloud-hosted Neon.tech PostgreSQL 18.6 instance in the Singapore region -- closest to India for low latency.

We have 9 live tables created via Alembic migrations: telemetry_readings for raw IoMT data, routing_decisions for every decision with AHP scores, hot_records for fast emergency access, cold_storage for archived data, and audit_log for the hash chain.

### Streamlit Web Dashboard

Our project includes a full real-time web portal built with Streamlit, accessible at localhost:8501.

After logging in with credentials admin and hospital123, the dashboard shows:
- EDGE vs CLOUD donut chart -- live routing distribution from the database
- Latency trend line chart -- LSTM-predicted latency over time
- Criticality scatter plot -- where each patient falls on the routing grid
- Metrics row -- total readings, percent EDGE routed, emergency override count
- Events table -- every routing decision, colour coded: red for emergency, yellow for cloud, green for EDGE

The dashboard auto-refreshes from Neon.tech -- a live view of the entire system.

### Testing

We have 99 tests with zero failures, covering unit tests for AHP and override rules, integration tests for FastAPI endpoints, alert dispatch tests, audit chain verification, and Locust load tests targeting p95 response under 200 milliseconds.

### CI/CD Pipeline

Every push to GitHub automatically triggers a 3-job pipeline: Lint with flake8, Test with all 99 pytest tests, and Build for Docker validation. The system never breaks silently.

### AWS Migration Readiness

Professor -- we have not built a prototype. Every component maps to a named AWS service. We have a lambda_handler.py in our repository that wraps the exact same Python routing logic as an AWS Lambda function -- with zero changes to core business logic.

FastAPI becomes API Gateway plus Lambda, LSTM becomes SageMaker endpoint, PostgreSQL becomes DynamoDB and S3, alerts become SNS, MQTT becomes AWS IoT Core, and the dashboard becomes QuickSight.

### Conclusion

We built a production-grade AI healthcare routing system that:
1. Ingests real-time IoMT telemetry via MQTT from 5 device types
2. Forecasts latency using LSTM trained on 2.83 million real RIPE Atlas measurements
3. Decides routing using AHP with CR = 0.037
4. Executes -- EDGE for critical patients, CLOUD for routine data
5. Alerts via live Telegram and Email
6. Stores in PostgreSQL with HIPAA-aligned hash-chained audit
7. Displays on live Streamlit web portal
8. Passes 99 automated tests with GitHub Actions CI/CD
9. Ready for AWS -- lambda handler written, every component mapped

This is not a classroom assignment. This is an industry-deployable healthcare cloud architecture system.

Thank you Professor. We are ready for your questions.

---
---

# PART C -- HOW THE WEB PORTAL WORKS

---

## Streamlit Dashboard -- Complete Guide

### How to Launch

Open THREE separate PowerShell terminals in the project folder:

TERMINAL 1 -- Start the API server:
  python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

TERMINAL 2 -- Start the data simulation (sends IoMT readings):
  python src/api/simulate_stream.py

TERMINAL 3 -- Launch the dashboard:
  python -m streamlit run dashboard/app.py

Your browser opens automatically at http://localhost:8501

### Login Screen
- Username: admin
- Password: hospital123
- The system verifies a JWT token against the Neon.tech users table

### Main Dashboard Screens After Login

METRICS ROW (top 4 cards):
  - Total Readings: count of all IoMT packets processed
  - EDGE Routed: number and % sent to local EDGE node
  - Cloud Routed: number and % sent to cloud
  - Emergency Overrides: count of criticality >= 9.0 events

EDGE vs CLOUD DONUT CHART:
  - Interactive Plotly pie chart
  - Hover for exact counts
  - Blue = CLOUD | Red = EDGE

LATENCY TREND LINE CHART:
  - X-axis = time | Y-axis = predicted latency (ms)
  - Red line at 300ms = network veto threshold
  - Shows LSTM predictions over time

CRITICALITY SCATTER PLOT:
  - X-axis = time | Y-axis = criticality score (0-10)
  - Red dots = EDGE routed | Blue dots = CLOUD routed
  - Separation visible above criticality 9.0 (emergency zone)

RECENT EVENTS TABLE:
  - Last 50 routing decisions from database
  - Columns: timestamp, device_id, criticality, latency_ms, decision, reason
  - Red row = emergency | Yellow = cloud | Green = EDGE

SIDEBAR CONTROLS:
  - Auto-refresh: on/off toggle
  - Refresh interval: 5 to 60 seconds
  - Device filter: view specific device data
  - Logout button

### How Data Gets to the Dashboard

IoMT Sensor
  --> MQTT
  --> FastAPI /ingest
  --> LSTM predicts latency
  --> AHP decides EDGE or CLOUD
  --> Data saved to Neon.tech PostgreSQL
  --> Streamlit reads from same DB every N seconds
  --> Charts update live on your browser

The dashboard only READS data. It never writes or modifies anything.

---

BCSE355L Cloud Architecture Design -- VIT University, October 2026
Team: Charles Jehanabad (24BIT0522) | Tanmay (24BIT0537) | [Third Member] (24BIT0543)
