# F1 Race Intelligence - Backend

The backend for **F1 Race Intelligence** provides a FastAPI REST API, PostgreSQL database models via SQLAlchemy 2.x, Alembic schema migrations, and stage-aware prediction endpoints.

---

## Architecture & Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI application entrypoint & middleware
│   ├── config.py        # Environment settings via pydantic-settings
│   ├── database.py      # SQLAlchemy engine, sessionmaker & Base
│   ├── models/          # SQLAlchemy 2.x ORM models
│   │   ├── __init__.py
│   │   ├── team.py
│   │   ├── driver.py
│   │   ├── race.py
│   │   ├── session.py
│   │   ├── session_result.py
│   │   └── prediction.py
│   └── api/
│       ├── __init__.py
│       └── health.py    # Health check endpoint
├── migrations/          # Alembic database migration scripts
│   ├── versions/
│   │   └── 0001_initial_schema.py
│   ├── env.py
│   └── script.py.mako
├── tests/
│   ├── test_health.py   # Health check API tests
│   └── test_database.py # Database schema & ORM relationship tests
├── alembic.ini          # Alembic migration configuration
├── .env.example         # Environment variable template
├── requirements.txt     # Python dependencies
└── README.md
```

---

## Quickstart Setup

### 1. Create Virtual Environment

From the `backend/` directory:

```bash
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Database Setup & PostgreSQL Configuration

### Database URL Format
The database connection string uses PostgreSQL with the `psycopg3` driver (`postgresql+psycopg://`):

```env
DATABASE_URL=postgresql+psycopg://<user>:<password>@localhost:5432/<dbname>
```

### Starting PostgreSQL via Docker Compose

From the root project directory:

```bash
docker-compose up -d postgres
```

This starts a PostgreSQL 16 container bound to port `5432` with database `f1_race_intelligence`.

### Running Database Migrations (Alembic)

```bash
# Apply migrations to update schema to head
alembic upgrade head

# Check current migration revision
alembic current

# Preview generated SQL without executing against database
alembic upgrade head --sql
```

---

## Database Schema Overview

| Model | Table | Key Fields & Constraints | Description |
|---|---|---|---|
| `Team` | `teams` | `id` (PK), `name` (Unique), `constructor_code` (Unique), `country` | F1 Constructor/Team metadata |
| `Driver` | `drivers` | `id` (PK), `driver_code` (Unique), `name`, `team_id` (FK -> teams.id) | F1 Driver details and team mapping |
| `Race` | `races` | `id` (PK), `season`, `round`, `race_name`, `circuit`, Unique(`season`, `round`) | Grand Prix weekend event info |
| `Session` | `sessions` | `id` (PK), `race_id` (FK -> races.id), `session_type` (`FP1`, `FP2`, `FP3`, `QUALIFYING`, `RACE`) | Specific race weekend session |
| `SessionResult` | `session_results` | `id` (PK), `session_id` (FK), `driver_id` (FK), `position`, `lap_time`, `sector_1/2/3`, `tyre`, `laps` | Timing & sector results per session |
| `Prediction` | `predictions` | `id` (PK), `race_id` (FK), `driver_id` (FK), `prediction_stage`, `win_probability`, `podium_probability`, `top5_probability`, `model_version` | Model prediction outputs per weekend stage |

---

## Running the Development Server

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- **Interactive Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health Check Endpoint**: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

---

## Running Tests

Run the full backend test suite:

```bash
pytest
```
