# AI-Based Multi-Cloud Migration Decision Framework for Healthcare

> **BCSE355L Cloud Architecture Design**
> Team: Charles ([@itscharles4](https://github.com/itscharles4) - 24BIT0522) · Tanmay Kapoor (24BIT0079) · Rani Gupta ([@grani27-m](https://github.com/grani27-m) - 24BIT0543)
> **Repository:** [github.com/itscharles4/AI-Based-Multi-Cloud-Migration-Decision-Framework-for-Healthcare-Enterprises_Cloud_Project_2026](https://github.com/itscharles4/AI-Based-Multi-Cloud-Migration-Decision-Framework-for-Healthcare-Enterprises_Cloud_Project_2026)

---

## 🏥 What This Project Does

An intelligent telemedicine workload offloader that:
1. **Predicts** network degradation using an LSTM neural network (Charles)
2. **Decides** edge vs cloud routing using AHP/MCDM (Tanmay)
3. **Executes** routing securely with full HIPAA-aligned audit trail (Rani)

---

## 📂 Repository Structure

```
telemedicine-cloud-project/
├── src/
│   ├── prediction/         ← Charles: LSTM forecasting
│   │   ├── data_generator.py
│   │   ├── preprocessing.py
│   │   ├── model.py
│   │   ├── train.py
│   │   └── predict_service.py
│   ├── decision/           ← Tanmay: AHP routing engine
│   │   ├── ahp.py
│   │   ├── override_rules.py
│   │   └── router.py
│   ├── execution/          ← Rani: edge/cloud/storage/auth/logging
│   │   ├── storage.py
│   │   ├── auth.py
│   │   ├── logger.py
│   │   ├── edge_node.py
│   │   └── cloud_node.py
│   └── api/                ← Integration layer
│       ├── main.py         (FastAPI)
│       └── simulate_stream.py
├── dashboard/
│   └── app.py              ← Streamlit dashboard
├── tests/
│   └── test_decision.py
├── data/
│   ├── raw/                ← telemetry_data.csv goes here
│   └── processed/          ← scaler.pkl, .npy files, app.db
├── results/graphs/         ← saved charts
├── logs/                   ← system.log
├── requirements.txt
└── README.md
```

---

## 🚀 How to Run Locally

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Generate synthetic data
```bash
cd telemedicine-cloud-project
python src/prediction/data_generator.py
```

### 3. Preprocess data
```bash
python src/prediction/preprocessing.py
```

### 4. Train the LSTM model
```bash
python src/prediction/train.py
# (or open in Google Colab for GPU acceleration)
```

### 5. Run unit tests
```bash
pytest tests/ -v
```

### 6. Start the API server
```bash
uvicorn src.api.main:app --reload
# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

### 7. Run the live stream simulation
```bash
python src/api/simulate_stream.py
```

### 8. Open the dashboard (in a separate terminal)
```bash
streamlit run dashboard/app.py
# Login: admin / hospital123
```

---

## 📊 System Architecture

```
IoMT Sensors → Edge Gateway
                    ↓
         [PREDICTION LAYER]   ← LSTM model (Charles)
         predicted_latency_ms
                    ↓
          [DECISION LAYER]    ← AHP engine (Tanmay)
         "EDGE" or "CLOUD"
                    ↓
       [EXECUTION LAYER]      ← Rani
    edge_node / cloud_node / storage / auth / logger
                    ↓
         [Streamlit Dashboard]
```

---

## ☁️ AWS Migration Plan

| Local Component | AWS Service | Change Required |
|---|---|---|
| FastAPI /ingest | AWS IoT Core (MQTT) | Replace POST with MQTT publish |
| predict_service.py | Amazon SageMaker | Replace local model with invoke_endpoint() |
| router.py | AWS Lambda | Wrap in lambda_handler() |
| edge_node.py | AWS IoT Greengrass | Deploy as Greengrass component |
| cloud_node.py | AWS Lambda | Deploy as standard Lambda |
| storage.py (SQLite) | Amazon S3 + DynamoDB | Replace with boto3 calls |
| auth.py | Amazon Cognito | Replace with Cognito User Pools |
| logger.py | Amazon CloudWatch | Replace with watchtower/boto3 |
| Streamlit dashboard | Amazon QuickSight | Point at DynamoDB/S3 |
| Local alert (print) | Amazon SNS | Replace with sns.publish() |

---

## 🔒 HIPAA Security Measures

- **Access control**: SHA-256 hashed passwords, UUID session tokens (→ Cognito on AWS)
- **Audit trail**: Every event logged as immutable JSON lines (→ CloudWatch on AWS)
- **Data minimisation**: PHI stays at edge during degraded network periods
- **Encryption**: In AWS migration, all data at rest uses KMS; transit uses TLS
- **Emergency override**: Criticality ≥ 9.0 bypasses all cost logic → local EDGE

---

## 📈 Key Results

After training:
- Model: 2-layer stacked LSTM (64→32 units)
- MAE and RMSE reported in `results/graphs/training_loss.png`
- AHP Consistency Ratio < 0.10 (confirmed in `src/decision/ahp.py`)

---

*Questions? Bring back the project guide (Section number) for targeted help.*
