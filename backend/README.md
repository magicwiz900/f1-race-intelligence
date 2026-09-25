# F1 Race Intelligence - Backend

The backend for **F1 Race Intelligence** provides a FastAPI REST API, PostgreSQL database models via SQLAlchemy 2.x, Alembic schema migrations, stage-aware prediction endpoints, and an F1 data ingestion layer.

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
│   ├── services/        # Business logic & external integrations
│   │   ├── __init__.py
│   │   └── f1_data/     # Ingestion layer modules
│   │       ├── __init__.py
│   │       ├── jolpica_client.py # HTTP client for Jolpica F1 API
│   │       ├── fastf1_service.py # FastF1 detailed session data service abstraction
│   │       ├── transformers.py   # Raw API response transformers
│   │       └── importer.py       # Idempotent DB data ingestion pipeline
│   └── api/
│       ├── __init__.py
│       └── health.py    # Health check endpoint
├── scripts/
│   ├── __init__.py
│   └── ingest_f1_data.py # CLI script for ingesting an F1 season
├── migrations/          # Alembic database migration scripts
│   ├── versions/
│   │   └── 0001_initial_schema.py
│   ├── env.py
│   └── script.py.mako
├── tests/
│   ├── test_health.py         # Health check API tests
│   ├── test_database.py       # Database schema & ORM relationship tests
│   ├── test_jolpica_client.py # Jolpica client mocked unit tests
│   └── test_f1_importer.py    # Importer idempotency & DB mapping tests
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

## Data Ingestion Layer

### Data Sources
1. **Primary Structured Data**: Jolpica F1 API (`https://api.jolpi.ca/ergast/f1`) for seasons, race calendars, drivers, constructors, and race results.
2. **Detailed Session Data**: FastF1 integration abstraction (`FastF1Service`) prepared for FP1/FP2/FP3/Qualifying/Race lap times, sector times, tyre compounds, and stints.

### Architecture
- **`JolpicaClient`**: Reusable HTTP client supporting timeout configuration, status code validation, custom exception handling (`JolpicaAPIError`, `JolpicaHTTPError`, `JolpicaParseError`), and response pagination.
- **`FastF1Service`**: Service abstraction wrapping FastF1 for detailed session loading on demand without downloading historical datasets during app startup.
- **`transformers`**: Pure transformation functions converting external raw JSON payloads into validated dictionary fields.
- **`F1DataImporter`**: Pipeline orchestrator for ingesting constructors, drivers, races, race sessions (`FP1`, `FP2`, `FP3`, `QUALIFYING`, `RACE`), and session results into PostgreSQL.

### How to Run Ingestion

```bash
# Ingest an F1 season (default 2025)
python -m scripts.ingest_f1_data --season 2025

# Ingest historical season e.g. 2024
python -m scripts.ingest_f1_data --season 2024
```

### Idempotency
The ingestion pipeline is strictly **idempotent**. Running the ingestion command multiple times will not create duplicate database records:
- **Teams**: Upserted based on unique `constructor_code` or `name`.
- **Drivers**: Upserted based on unique `driver_code`.
- **Races**: Upserted using the unique (`season`, `round`) constraint (`uq_race_season_round`).
- **Sessions**: Upserted based on (`race_id`, `session_type`).
- **Session Results**: Upserted based on (`session_id`, `driver_id`).

### Mocked Unit Testing
Unit tests in `tests/test_jolpica_client.py` and `tests/test_f1_importer.py`:
- Use `unittest.mock` to mock Jolpica HTTP network calls (no internet dependency).
- Use an isolated in-memory SQLite database session (`test_db_session` / `db_session`) to test model creation, driver-to-team links, and idempotency without requiring a live PostgreSQL instance.

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
