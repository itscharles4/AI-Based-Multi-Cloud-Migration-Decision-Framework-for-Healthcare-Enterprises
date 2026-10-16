# Telemedicine Workload Offloader

**AI-Based Multi-Cloud Migration Decision Framework for Healthcare Enterprises using Multi-Criteria Decision Intelligence**

BCSE355L Cloud Architecture Design · Course Instructor: Dr. Priya V · Vellore Institute of Technology, Vellore

| Student | Register no. | Branch | Focus |
|---|---|---|---|
| Charles Jehanabad | 24BIT0522 | `feature/student1` | AI prediction, datasets, device simulation |
| Tanmay Kapoor | 24BIT0079 | `feature/student2` | MCDM decision engine (AHP, override, tests) |
| Rani Gupta | 24BIT0543 | `feature/student3` | Execution layer, security, alerts, dashboard |

## What it does

For every IoMT reading, the system decides whether to process it at the **hospital edge** or in the **cloud**:

1. An **LSTM** predicts the next network latency from the last 20 readings (trained on 2,830,022 real RIPE Atlas measurements).
2. **Stage A – hard vetoes:** criticality ≥ 9.0 (emergency override) or predicted latency ≥ 300 ms (network veto) always route to the edge.
3. **Stage B – AHP scoring:** weights 0.6396 (criticality), 0.2583 (latency), 0.1021 (cloud cost); consistency ratio 0.037.
4. The **execution layer** runs the edge or cloud node, stores the result, raises Telegram/e-mail alerts for emergencies and appends a SHA-256 hash-chained audit record.
5. A **dashboard** shows live routing results.

Research prototype: simulated and public data only; HIPAA-aligned design, not certified; not clinically validated.

## Repository structure (course guideline) and task allocation

```
Telemedicine_Cloud_Project_2026/
├── README.md, LICENSE, .gitignore          # README: Student 3 · LICENSE/.gitignore/requirements: Student 2
├── docs/
│   ├── Project_Report.docx                 # all students
│   ├── Literature_Survey.docx              # P1–P5 Student 1 · P6–P10 Student 2 · P11–P15 Student 3
│   ├── Research_Gap_Student1.docx
│   ├── Research_Gap_Student2.docx
│   ├── Research_Gap_Student3.docx
│   ├── Objectives.docx
│   └── Novelty.docx
├── architecture/
│   ├── AWS_Architecture.png                # Figure 1
│   ├── System_Architecture.png             # Figure 2
│   └── Workflow.png                        # Figure 3
├── dataset/
│   ├── raw/  processed/
│   └── dataset_description.pdf             # Student 1
├── src/
│   ├── frontend/                           # dashboard – Student 3
│   ├── backend/
│   │   ├── decision/                       # AHP, override, network veto, tests – Student 2
│   │   ├── APIs/  Database/  Authentication/   # Student 3
│   │   └── mqtt/                           # MQTT consumer – Student 3
│   ├── ml_model/                           # preprocessing, train, predict, model – Student 1
│   └── aws/
│       ├── edge_node/  cloud_node/         # Greengrass / Lambda stand-ins – Student 3
│       ├── alerts/  audit/  logging/       # Student 3
│       └── lambda_handler.py               # Student 2
├── results/                                # graphs (S1 model, S2 routing chart), screenshots, accuracy.xlsx, test/load results (S3)
└── presentation/                           # review slides – all
```

## Branches and workflow

```
main
 └── develop
      ├── feature/student1   (Charles)
      ├── feature/student2   (Tanmay Kapoor)
      └── feature/student3   (Rani Gupta)
```

* Each student commits only to their own feature branch (about 20–30 meaningful commits, regular weekly commits).
* Raise a pull request from the feature branch into `develop`; a teammate reviews it before merge (at least 2 pull requests per student).
* Never commit directly to `main` or `develop`. Resolve merge conflicts in the pull request.
* When `develop` is stable, merge it into `main` and tag the release, e.g. `v1.0-Phase1`.

## Run locally

> Paths below match the current code layout; update them if folders are renamed to the structure above.

```bash
cp .env.example .env                                      # fill in your own values; never commit .env
pip install -r requirements.txt
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload   # API
python src/api/simulate_stream.py                         # simulated IoMT stream
python -m streamlit run dashboard/app.py                  # dashboard at http://localhost:8501
pytest -q                                                 # automated tests
docker compose up -d                                      # full stack (API, database, Redis, MQTT, Prometheus, Grafana)
```

## AWS services (target architecture)

| Component now | AWS target | Status |
|---|---|---|
| MQTT broker (Mosquitto) | AWS IoT Core | Planned |
| FastAPI `/ingest` | Amazon API Gateway | Planned |
| LSTM model | Amazon SageMaker | Planned |
| AHP routing function | AWS Lambda (`lambda_handler.py`) | Handler written, not deployed |
| Edge node | AWS IoT Greengrass | Planned |
| Hot / cold storage | Amazon DynamoDB / Amazon S3 | Planned |
| JWT + roles | Amazon Cognito + IAM | Planned |
| Telegram / e-mail alerts | Amazon SNS | Planned |
| Prometheus | Amazon CloudWatch | Planned |
| Dashboard | Amazon QuickSight | Planned |

## Status

* **Implemented locally:** prediction layer, decision engine, execution layer, authentication, audit chain, alerts, dashboard prototype, Docker Compose, CI (lint, test, Docker build).
* **Not yet done:** AWS deployment, forecast accuracy against baselines, load test, Grafana dashboards.

## Security

No credentials, tokens or personal data are stored in this repository. Configuration comes from environment variables (`.env` is git-ignored).
