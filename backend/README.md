# F1 Race Intelligence - Backend

The backend for **F1 Race Intelligence** provides a FastAPI REST API serving F1 race predictions, session-by-session telemetry analytics, dynamic win probability progression, and driver/team comparisons.

---

## Architecture & Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI application entrypoint & middleware configuration
│   ├── config.py        # Environment & application configuration via pydantic-settings
│   └── api/
│       ├── __init__.py
│       └── health.py    # Health check endpoint
├── tests/
│   ├── __init__.py
│   └── test_health.py   # Health endpoint unit tests
├── .env.example         # Example environment variables
├── requirements.txt     # Python dependencies
└── README.md
```

---

## Quickstart Setup

### 1. Create Virtual Environment

From the `backend/` directory (or workspace root):

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

## Environment Configuration

Copy `.env.example` to `.env` if local custom settings are required:

```bash
cp .env.example .env
```

Available environment variables:
* `APP_NAME`: Application title (default: `"F1 Race Intelligence API"`)
* `APP_ENV`: Deployment environment (default: `"development"`)
* `DATABASE_URL`: PostgreSQL connection string (placeholder for future steps)
* `API_KEY`: Secret key placeholder
* `CORS_ORIGINS`: Allowed origins list for frontend CORS communication

---

## Running the Server

Start the development server with auto-reload:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- **Interactive API Documentation (Swagger UI)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Alternative ReDoc Docs**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## Running Tests

Run the backend test suite using `pytest`:

```bash
pytest
```

---

## API Endpoints

### Health Check

* **Endpoint**: `GET /api/health`
* **Description**: Verifies backend service status and health readiness.
* **Response (200 OK)**:
  ```json
  {
    "status": "ok",
    "service": "f1-race-intelligence"
  }
  ```
