<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/PyTorch-2.x-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white"/>
  <img src="https://img.shields.io/badge/FastAPI-0.128-009688?style=for-the-badge&logo=fastapi&logoColor=white"/>
  <img src="https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black"/>
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white"/>
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge"/>
</p>

<h1 align="center">🛡️ UBA & Insider Threat Detection — "Vigilant Lens"</h1>

<p align="center">
  <b>An end-to-end machine-learning system that learns each user's behavioural baseline and flags insider-threat activity, with a context-aware risk-scoring engine, a FastAPI backend, and a React SOC dashboard.</b>
</p>

---

## 🔍 Overview

**Vigilant Lens** is a User Behaviour Analytics (UBA) and Insider Threat Detection (ITD) platform. It generates synthetic CERT-style security logs, engineers per-user behavioural features, trains role-specific LSTM autoencoders to learn "normal", and converts reconstruction anomalies into **explainable, context-aware risk scores (0–100)** mapped to the MITRE ATT&CK framework. Findings are served through a FastAPI backend and an interactive React dashboard.

### The scenario it detects

The synthetic generator injects a labelled insider threat: **user `U105`** begins **after-hours data exfiltration** in the second half of the month — bulk **file copies to removable media** plus **USB device connects**, occurring outside working hours. The pipeline is designed to surface exactly this pattern.

> **Result on the injected scenario (reproducible via the pipeline below):** U105 is ranked **#1 of 100 users** (total risk ≈ 147, well clear of the next user ≈ 70), all of its malicious days are flagged, and **no normal user crosses the alert threshold** — precision/recall/F1 = **1.00 / 1.00 / 1.00** on this benchmark, with drift detection flagging only ~7/100 users (including U105).
>
> This is a **single synthetic scenario**, not a generalisation claim: the number demonstrates that the feature engineering, model, and scoring engine are correctly wired end-to-end and cleanly separate the injected threat from normal behaviour.

---

## 🏗️ Architecture

```
 Raw CSV logs            Feature engineering          Role LSTM autoencoders
 (logon/file/http/  ──►  daily per-user features  ──►  (employee/admin/          ──┐
  device)                far,eds,iav,oaf,login_ent      contractor/global)        │
                         file_copy_count, usb_count,    reconstruction error      │
                         removable_media_count,                                    ▼
                         after_hours_ratio, ...                          Risk-scoring engine
                                                                         (role-relative base risk
 React dashboard   ◄───  FastAPI  ◄───  risk_report_*.csv  ◄────────────  × context multipliers,
 (Vite + Tailwind)       REST API       + evaluation report               MITRE mapping, alerts,
                                                                          drift detection)
```

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🧬 **Synthetic data generation** | Deterministic (`seed=42`) CERT-style logs with realistic personas and a labelled, after-hours insider-threat scenario. |
| 🧠 **Role-specific LSTM autoencoders** | Separate models per role learn role-appropriate "normal"; anomalies = reconstruction error normalised **relative to each role's own error distribution** (no score saturation). |
| 🎯 **Context-aware risk scoring** | Role · after-hours-ratio · activity (file-copy / USB / delete) · behavioural-volume multipliers → an explainable 0–100 score, with a file-copy + USB + after-hours pattern override. |
| 🧭 **MITRE ATT&CK mapping** | Detected activity is mapped to tactics/techniques (Exfiltration, Impact, …). |
| 📈 **Behavioural drift detection** | Flags users whose recent risk deviates from their own earlier baseline (σ-based), not from the crowd. |
| ⚡ **FastAPI backend** | Async REST API with rate limiting, request-ID correlation, audit logging, graceful degradation, and Swagger docs. |
| 📊 **React SOC dashboard** | Dark "Vigilant Lens" UI: dashboard, risk heatmap, forensics, alerts, users, settings — all bound to real API data. |
| 🐳 **Docker-ready** | `docker compose up --build` brings up the API + an nginx-served frontend that reverse-proxies `/api`. |
| 🧪 **Test suite** | Pytest unit/integration tests across the pipeline, risk engine, security, and API. |

---

## 🛠️ Tech Stack

| Layer | Technologies |
|---|---|
| **Data** | Polars · Pandas · NumPy · PyArrow · Faker |
| **ML** | PyTorch · scikit-learn · XGBoost · SHAP |
| **Backend** | FastAPI · Uvicorn · Pydantic · cryptography |
| **Frontend** | React 18 · Vite 5 · Tailwind v4 · Recharts · lucide-react |
| **Infra** | Docker · Docker Compose · nginx |
| **Testing** | Pytest · HTTPX |

---

## 📁 Project Structure

```
uba-insider-threat-detection/
├── src/
│   ├── api/                 # FastAPI backend (main, routers, services, schemas)
│   ├── data_pipeline/       # generator, normalization, feature_engineering, ...
│   ├── models/              # lstm_autoencoder, train_role_lstm, thresholding, ...
│   ├── risk_engine/         # scoring, aggregation (drift), run_risk
│   ├── evaluation/          # evaluate_system (precision/recall/F1 + report)
│   ├── security/            # privacy (pseudonymization/erasure), engine
│   ├── telemetry/           # optional real-time agent, sqlite store, integrity engine
│   └── utils/               # config loader
├── website/                 # React + Vite dashboard (nginx Dockerfile + proxy)
├── data/                    # raw/ processed/ risk_output/  (generated; gitignored)
├── models/                  # trained artifacts (generated; gitignored)
├── tests/                   # pytest suite
├── config.yaml              # central configuration
├── requirements.txt         # Python dependencies
├── Dockerfile               # backend image
├── docker-compose.yml       # full stack
└── .env.example             # environment template
```

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.11+**
- **Node.js 18+**

### 1. Python environment
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Frontend
```bash
cd website && npm install && cd ..
```

### 3. Environment (optional)
```bash
cp .env.example .env   # then edit if you use the optional LLM features / set UBA_PII_SALT
```

---

## ⚙️ Run the pipeline

Run the steps in order (uses `config.yaml` for all parameters):

```bash
# 1) Generate synthetic security logs (deterministic)
python -m src.data_pipeline.generator

# 2) Build the unified timeline + daily behavioural features
python -m src.data_pipeline.normalization

# 3) Train role-specific LSTM autoencoders
python -m src.models.train_role_lstm

# 4) Score risk (LSTM inference → context-aware risk + alerts + drift)
python -m src.risk_engine.run_risk

# 5) Evaluate against ground truth (writes evaluation_report.md + .json)
python -m src.evaluation.evaluate_system
```

Then start the services:

```bash
# Backend API
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend (new terminal)
cd website && npm run dev
```

- **API**: http://localhost:8000 · **Docs**: http://localhost:8000/docs
- **Dashboard**: http://localhost:5173

> On Windows you can also just run `run.bat` (launches both) or `start.bat` (API only).

---

## 🎯 Risk Scoring

Reconstruction error from the per-role LSTM is converted to a **base risk** that is normalised against **that role's own error distribution** (mean → threshold → 100), then modulated by context:

```
Final Risk = Base Risk × Role × After-Hours × Activity × Behavioural-Volume
```

| Factor | Signal | Effect |
|---|---|---|
| **Role** | Admin / Contractor / Employee | higher-privilege roles weighted up |
| **After-hours** | `after_hours_ratio` (gated by event volume) | elevates sustained off-hours activity |
| **Activity** | `file_copy_count`, `usb_count`, `delete_count` | file-copy / USB / deletion multipliers |
| **Pattern override** | file-copy **and** USB **and** after-hours | forces a high-risk classification |

Alerts use persistence + cooldown to control fatigue; thresholds (Medium 70 / High 85 / Critical 95) are in `config.yaml`.

---

## 🔌 API Endpoints (selected)

| Endpoint | Description |
|---|---|
| `GET /health` | Readiness probe |
| `GET /api/stats` · `GET /api/dashboard/summary` | Dashboard statistics |
| `GET /api/users/risk` · `GET /api/users/{id}/profile` | User risk profiles |
| `GET /api/users/{id}/timeline` | Per-user event timeline |
| `GET /api/events/risk` | Risk-scored events |
| `GET /api/alerts` | Alert queue (severity filter + pagination) |
| `GET /api/analysis/user/{id}` · `/analysis/drift-status` | Risk history & drift |
| `GET /api/models/status` | Model health/metadata |
| `GET /api/v1/telemetry/*` | Optional live-telemetry endpoints |

Full interactive docs at `/docs`.

---

## 🖥️ Dashboard

| Page | Route | Description |
|---|---|---|
| Dashboard | `/dashboard` | KPIs, top threats, recent alerts, (optional) live sessions |
| Risk Heatmap | `/heatmap` | User × time risk matrix |
| Forensics | `/forensics` | Per-user deep dive, timeline, MITRE (data-driven) |
| Alerts | `/alerts` | Alert queue with severity filtering |
| Users | `/users` | Ranked user risk leaderboard |
| Settings | `/settings` | Model status, thresholds, admin actions |

---

## 🐳 Docker

```bash
docker compose up --build
```

- **backend** (`uba-backend`) → http://localhost:8000
- **frontend** (`uba-frontend`, nginx) → http://localhost:5173 — reverse-proxies `/api` to the backend, so no CORS setup is needed.

The compose file mounts `./data` and `./models` into the backend, so it serves whatever the pipeline produced locally. For a clean deployment, run the pipeline first (or bake the artifacts into the image).

---

## 🔐 Security Notes (read before deploying)

This is a **demonstration / research** project. Before any real use:
- **RBAC** is a demo control via the `X-User-Role` header — replace with real authentication.
- The **real-time telemetry agent** captures keystroke/mouse *timing* and window titles; it is **off by default** and gated behind an explicit consent flag. Only enable with informed consent and a lawful basis.
- **PII pseudonymization** uses a salt from `UBA_PII_SALT` (a dev-only default is provided) — set a strong secret in production. Encryption keys must not be committed; `.env`, `*.db`, and `data/security_output/` are gitignored and docker-ignored.

---

## 🗺️ MITRE ATT&CK Mapping

| Activity | Tactic | Technique |
|---|---|---|
| File copy → USB | Exfiltration (TA0010) | Exfiltration Over Physical Medium (T1052) |
| USB connect | Exfiltration (TA0010) | Hardware Additions (T1200) |
| After-hours logon | Credential Access (TA0006) | Valid Accounts (T1078) |
| File delete | Impact (TA0040) | Data Destruction (T1485) |

---

## 🧪 Testing

```bash
pytest tests/ -q
```

Covers the data pipeline, risk engine, aggregation/drift, security, and API endpoints.

---

## 📄 License

MIT — see [LICENSE](LICENSE).

<p align="center"><b>Vigilant Lens · built for enterprise cybersecurity</b></p>
