# F1 Race Intelligence

## Project Overview
**F1 Race Intelligence** is a full-stack web application designed to analyze Formula 1 race-weekend data and dynamically predict race outcomes as each weekend session unfolds.

The system dynamically updates driver race win probabilities, podium probabilities, top-5 finishes, and finishing positions across distinct race-weekend stages:
1. `PRE_FP1`
2. `POST_FP1`
3. `POST_FP2`
4. `POST_FP3`
5. `POST_QUALIFYING`
6. `FINAL`

---

## High-Level Architecture

```
F1 Data Sources (FastF1 / Jolpica / OpenF1)
                 ↓
          Data Ingestion
                 ↓
            PostgreSQL
                 ↓
       Feature Engineering
                 ↓
        ML Prediction Model
                 ↓
         FastAPI REST API
                 ↓
          React Frontend
```

---

## Tech Stack

* **Frontend**: React, Vite, Tailwind CSS, Recharts
* **Backend**: Python, FastAPI, SQLAlchemy, Pydantic, Alembic
* **Database**: PostgreSQL
* **Machine Learning**: Python, pandas, numpy, scikit-learn, joblib (optional XGBoost)
* **F1 Data**: Evaluated from official/community APIs (e.g., FastF1, Jolpica, OpenF1) without data fabrication.

---

## Folder Structure

```
f1-race-intelligence/
├── frontend/     # React + Vite UI dashboard
├── backend/      # FastAPI REST API & database models
├── ml/           # Feature engineering & ML prediction models
├── data/         # Raw and processed F1 dataset storage
├── docs/         # System architecture & API documentation
├── .gitignore
└── README.md
```

---

## Development Principles
* **Modularity**: Strict separation between Frontend, Backend, ML logic, and Data ingestion.
* **No Data Leakage**: ML features strictly reflect information available up to the active session stage.
* **Authentic F1 Data**: No missing data fabrication or synthetic hallucination.
* **Environment Variables**: Managed securely without hardcoded API keys or credentials.