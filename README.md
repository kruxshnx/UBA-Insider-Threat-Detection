<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/PyTorch-2.10-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white"/>
  <img src="https://img.shields.io/badge/FastAPI-0.128-009688?style=for-the-badge&logo=fastapi&logoColor=white"/>
  <img src="https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black"/>
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white"/>
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge"/>
</p>

<h1 align="center">🛡️ UBA & Insider Threat Detection System</h1>

<p align="center">
  <b>An end-to-end Machine Learning system for detecting anomalous user behavior and potential insider threats in enterprise environments.</b>
</p>

<p align="center">
  Built with LSTM Autoencoders · Isolation Forest · Risk Scoring Engine · FastAPI · React Dashboard
</p>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [System Architecture](#-system-architecture)
- [Key Features](#-key-features)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
- [Usage](#-usage)
- [ML Models](#-ml-models)
- [Risk Scoring Engine](#-risk-scoring-engine)
- [API Endpoints](#-api-endpoints)
- [Frontend Dashboard](#-frontend-dashboard)
- [Docker Deployment](#-docker-deployment)
- [Configuration](#-configuration)
- [Testing](#-testing)
- [MITRE ATT&CK Mapping](#-mitre-attck-mapping)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🔍 Overview

**User Behavior Analytics (UBA) & Insider Threat Detection (ITD)** is a comprehensive security analytics platform that leverages machine learning to identify suspicious user activities within an organization. The system generates synthetic CERT-like security logs, processes them through a multi-model ML pipeline, calculates contextual risk scores, and presents findings through an interactive React dashboard.

### The Problem

Insider threats account for **60% of data breaches** and are among the hardest to detect because malicious insiders use legitimate credentials. Traditional rule-based systems generate excessive false positives and miss sophisticated attack patterns.

### The Solution

This system uses **behavioral baselines** and **deep learning** to learn what "normal" looks like for each user, then flags deviations — even subtle ones — with a context-aware risk scoring engine.

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         UBA & ITD SYSTEM                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   📦 DATA LAYER              ⚙️ PROCESSING              🧠 ML MODELS   │
│   ─────────────              ─────────────              ─────────────   │
│   ┌─────────────┐            ┌─────────────┐            ┌───────────┐   │
│   │  Raw CSVs   │ ────────►  │ Normalization│ ────────► │  LSTM     │   │
│   │  (logon,    │            │ (Parquet)   │            │ Autoenc.  │   │
│   │   file,     │            └─────────────┘            └───────────┘   │
│   │   http,     │                                             │         │
│   │   device)   │                                             ▼         │
│   └─────────────┘                                       ┌───────────┐   │
│                                                         │ Isolation │   │
│                                                         │ Forest    │   │
│                                                         └───────────┘   │
│                                                               │         │
│   🎯 RISK ENGINE             🔌 API LAYER              🖥️ FRONTEND    │
│   ─────────────              ─────────────              ─────────────   │
│   ┌─────────────┐            ┌─────────────┐            ┌───────────┐   │
│   │  Scoring    │ ◄───────── │  FastAPI    │ ◄───────── │  React    │   │
│   │  Engine     │            │  Endpoints  │            │  Dashboard│   │
│   └─────────────┘            └─────────────┘            └───────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🧬 **Synthetic Data Generation** | CERT-like security logs with realistic user personas, work patterns, and injected threat scenarios |
| 🤖 **Dual ML Pipeline** | LSTM Autoencoder (deep learning) + Isolation Forest (ensemble) for robust anomaly detection |
| 🎯 **Contextual Risk Scoring** | Role-based, time-aware, activity-weighted risk scores (0–100) with exponential decay |
| ⚡ **FastAPI Backend** | High-performance async REST API serving risk data and analytics |
| 📊 **Interactive Dashboard** | React-based cybersecurity dashboard with heatmaps, forensics timeline, and alert management |
| 🗺️ **MITRE ATT&CK Mapping** | Detected activities are mapped to MITRE ATT&CK tactics and techniques |
| 🐳 **Docker Ready** | Full containerization with Docker Compose for one-command deployment |
| 🧪 **Testing Suite** | Pytest-based unit and integration tests |

---

## 🛠️ Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Data Processing** | Polars · Pandas · NumPy · PyArrow |
| **Machine Learning** | PyTorch · scikit-learn · XGBoost · SHAP |
| **Backend API** | FastAPI · Uvicorn · Pydantic |
| **Frontend** | React 18 · Vite · Recharts · React Router |
| **Serialization** | Parquet · CSV · Joblib |
| **Infrastructure** | Docker · Docker Compose |
| **Testing** | Pytest · HTTPX |

---

## 📁 Project Structure

```
uba-insider-threat-detection/
│
├── src/                           # Source Code
│   ├── api/                       # FastAPI Backend
│   │   ├── main.py                # App entry point
│   │   ├── config.py              # API settings & CORS
│   │   ├── routers/               # Route handlers
│   │   │   ├── stats.py           # GET /api/stats
│   │   │   ├── users.py           # GET /api/users/risk
│   │   │   └── events.py          # GET /api/events/risk
│   │   ├── schemas/               # Pydantic response models
│   │   └── services/              # Data loading logic
│   │
│   ├── data_pipeline/             # Data Generation & Processing
│   │   ├── generator.py           # Synthetic CERT log generator
│   │   └── normalization.py       # Unified timeline builder
│   │
│   ├── models/                    # Machine Learning
│   │   ├── lstm_autoencoder.py    # LSTM Autoencoder model
│   │   ├── baseline.py            # Isolation Forest / One-Class SVM
│   │   ├── train_lstm.py          # LSTM training script
│   │   └── train_baseline.py      # Baseline training script
│   │
│   ├── risk_engine/               # Risk Scoring
│   │   ├── scoring.py             # Score calculation logic
│   │   └── run_risk.py            # Risk pipeline runner
│   │
│   ├── evaluation/                # Model evaluation
│   ├── security/                  # Security & governance
│   └── utils/                     # Shared utilities
│
├── data/
│   ├── raw/                       # Generated CSV logs
│   ├── processed/                 # Parquet master timeline
│   └── risk_output/               # Risk score reports
│
├── models/
│   ├── baseline/                  # Saved Isolation Forest model
│   ├── lstm/                      # Saved LSTM model + scaler
│   └── hybrid/                    # Hybrid model artifacts
│
├── website/                       # React Frontend (Vite)
│   └── src/
│       ├── pages/                 # Dashboard, Heatmap, Forensics, etc.
│       ├── components/            # Reusable UI components
│       └── services/              # API client
│
├── tests/                         # Unit & Integration Tests
├── config.yaml                    # Central configuration
├── requirements.txt               # Python dependencies
├── Dockerfile                     # Backend container
├── docker-compose.yml             # Full stack orchestration
└── README.md                      # Project documentation
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for the frontend)
- **Git**

### 1. Clone the Repository

```bash
git clone https://github.com/kruxshnx/UBA-Insider-Threat-Detection.git
cd UBA-Insider-Threat-Detection
```

### 2. Set Up the Python Environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Set Up the Frontend

```bash
cd website
npm install
cd ..
```

---

## ⚙️ Usage

### Run the Complete Pipeline

Run each step individually:

```bash
# Step 1: Generate synthetic security logs
python -m src.data_pipeline.generator

# Step 2: Normalize and merge into master timeline
python -m src.data_pipeline.normalization

# Step 3: Train the LSTM Autoencoder
python -m src.models.train_lstm

# Step 4: Train baseline models (Isolation Forest)
python -m src.models.train_baseline --model isolation_forest

# Step 5: Run the risk scoring engine
python -m src.risk_engine.run_risk

# Step 6: Start the backend API server
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# Step 7: Start the frontend (in a new terminal)
cd website && npm run dev
```

Once running:
- **Backend API**: http://localhost:8000
- **API Docs (Swagger)**: http://localhost:8000/docs
- **Frontend Dashboard**: http://localhost:5173

---

## 🧠 ML Models

### LSTM Autoencoder (Primary Model)

A sequence-based deep learning model trained on normal user behavior patterns. Anomalies are detected when the reconstruction error exceeds a learned threshold.

```
INPUT [t1..t10] ──► ENCODER (2×LSTM, H=32) ──► LATENT [32] ──► DECODER ──► OUTPUT [t1'..t10']

                    Loss = MSE(Input, Output)
                    High Loss = Anomaly 🚨
```

| Hyperparameter | Value |
|----------------|-------|
| Sequence Length | 10 |
| Hidden Dimension | 32 |
| LSTM Layers | 2 |
| Batch Size | 64 |
| Epochs | 10 |
| Learning Rate | 0.001 |

**Features**: `hour` (scaled), `day_of_week` (scaled), `source_idx` (Logon=0, File=1, Http=2, Device=3)

### Isolation Forest (Baseline Model)

An ensemble tree-based algorithm that isolates anomalies by random recursive partitioning. Anomalous points require fewer splits to isolate.

| Parameter | Value |
|-----------|-------|
| Estimators | 100 |
| Contamination | 5% |

---

## 🎯 Risk Scoring Engine

Raw anomaly scores are transformed into actionable intelligence through a multi-factor risk scoring formula:

```
Final Risk = Base Risk × Role Multiplier × Time Multiplier × Activity Multiplier
```

### Contextual Multipliers

| Factor | Condition | Multiplier |
|--------|-----------|:----------:|
| **Role** | Admin | 1.5× |
| | Contractor | 1.2× |
| | Employee | 1.0× |
| **Time** | Before 7 AM or After 8 PM | 1.5× |
| **Activity** | File Copy to USB | 4.0× |
| | USB Device Connect | 3.0× |
| | File Delete | 2.0× |

### Risk Decay

Older events receive exponentially decaying scores to prevent stale alerts:

```
Decayed Score = Score × 0.9^(days_since_event)
```

### Alert Thresholds

| Severity | Score Range |
|----------|:-----------:|
| 🟡 Medium | 70–84 |
| 🟠 High | 85–94 |
| 🔴 Critical | 95–100 |

---

## 🔌 API Endpoints

| Endpoint | Method | Description |
|----------|:------:|-------------|
| `/` | `GET` | Health check |
| `/api/stats` | `GET` | Dashboard summary statistics |
| `/api/users/risk` | `GET` | Top risky users with scores |
| `/api/events/risk` | `GET` | Individual risky events |

**Interactive Documentation**: Visit `http://localhost:8000/docs` for Swagger UI.

---

## 🖥️ Frontend Dashboard

A modern cybersecurity-themed React dashboard with multiple views:

| Page | Route | Description |
|------|-------|-------------|
| **Dashboard** | `/` | Real-time stats, alerts, and trend charts |
| **Risk Heatmap** | `/heatmap` | User × Hour risk visualization matrix |
| **Forensics** | `/forensics` | Deep-dive investigation with activity timeline |
| **Alerts** | `/alerts` | Alert queue with severity filtering |
| **Users** | `/users` | Ranked user risk leaderboard |
| **Settings** | `/settings` | System configuration and preferences |

---

## 🐳 Docker Deployment

Deploy the entire stack with a single command:

```bash
docker-compose up --build
```

This spins up:
- **Backend** (`uba-backend`): FastAPI + ML models on port `8000`
- **Frontend** (`uba-frontend`): React dashboard on port `5173`

The backend includes a health check and auto-restart policy.

---

## ⚙️ Configuration

All system parameters are centralized in `config.yaml`:

```yaml
data_generation:
  num_users: 100
  days_to_simulate: 30
  insider_threat_user: "U105"

lstm:
  sequence_length: 10
  hidden_dim: 32
  epochs: 10

risk_scoring:
  role_multipliers:
    Admin: 1.5
    Contractor: 1.2
  after_hours_multiplier: 1.5
  decay_rate: 0.9

alerting:
  critical_threshold: 95
  high_threshold: 85
  medium_threshold: 70
```

---

## 🧪 Testing

Run the test suite with:

```bash
pytest tests/ -v
```

Test coverage includes:
- Data pipeline validation
- Model training and inference
- Risk score calculation
- API endpoint responses

---

## 🗺️ MITRE ATT&CK Mapping

Detected activities are automatically mapped to the MITRE ATT&CK framework:

| Activity | Tactic | Technique |
|----------|--------|-----------|
| File Copy → USB | Exfiltration (TA0010) | Exfiltration Over Physical Medium (T1052) |
| USB Connect | Exfiltration (TA0010) | Hardware Additions (T1200) |
| After-Hours Logon | Credential Access (TA0006) | Valid Accounts (T1078) |
| File Delete | Impact (TA0040) | Data Destruction (T1485) |

---

## 📊 Insider Threat Scenario

The system includes a pre-injected threat scenario for validation:

> **User U105** begins data exfiltration after day 25:
> - Bulk copies 20+ files with `CONFIDENTIAL_` prefix
> - Transfers files to removable USB media
> - Activity occurs during suspicious timing (just before logout)

The ML models and risk engine are designed to detect this pattern and escalate U105 to **Critical** risk status.

---

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <b>Built with ❤️ for enterprise cybersecurity</b>
</p>
