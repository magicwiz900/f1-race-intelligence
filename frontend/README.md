# F1 Race Intelligence — Frontend Module

The frontend for **F1 Race Intelligence** is a production motorsport analytics command center interface providing live race prediction timing boards, weekend stage timeline progression controls, probability distribution analytics, and driver telemetry inspectors.

---

## Architecture & Visual System

* **Visual Identity**: Dark carbon motorsport theme (`#07090e` base, `#0e131f` card panels, `#1b2436` subtle telemetry borders).
* **Typography**: Dual technical typography featuring **Orbitron** & **Rajdhani** for motorsport headers, **Inter** for readable UI text, and **Roboto Mono** for timing values.
* **Team Accents**: Dynamic team color pill indicators for McLaren (`#FF8000`), Red Bull (`#3671C6`), Ferrari (`#E8002D`), Mercedes (`#27F4D2`), Aston Martin (`#229971`), Alpine (`#0093CC`), Williams (`#64C4FF`), RB (`#6692FF`), Sauber (`#52E252`), and Haas (`#B6BABD`).
* **Zero Build Overhead**: Implemented as a clean HTML5 + CSS3 + modern JavaScript application served directly by FastAPI or standalone browsers.

---

## Key Features

1. **Race Control Header**:
   - Grand Prix selector listing 2025 F1 calendar rounds.
   - Race summary displaying season, round, circuit, and race date.
   - Live backend status indicator (`PREDICTION MODEL OK`).

2. **Race-Weekend Stage Segmented Timeline**:
   - Stage progression control: `PRE FP1` → `POST FP1` → `POST FP2` → `POST FP3` → `POST QUALIFYING`.
   - Dynamic API stage query updating predictions on stage switch.

3. **Motorsport Timing Board Table**:
   - Driver position rank badges (`P1`, `P2`, `P3` podium highlights).
   - Driver 3-letter code tags and team indicators.
   - Telemetry columns: `RACE SHARE %`, `RAW WIN %`, `PODIUM %`, `TOP 5 %`, `PRED FINISH`.
   - Interactive column sorting.

4. **Analytics Command Center**:
   - **Win Race-Share Distribution Bar Chart**: Horizontal bar chart comparing relative race-share probabilities across top drivers ($\sum P_{\text{share}} \approx 100\%$).
   - **Data Availability Matrix**: Real-time status matrix showing active session data feeds (`Historical Form`, `FP1`, `FP2`, `FP3`, `Qualifying`).

5. **Driver Telemetry Inspector Drawer**:
   - Interactive modal popup displaying a driver's detailed prediction specs and model output.

---

## API Configuration & Running

### Automatic API Resolution
The application automatically resolves the API base URL:
* Configurable via `window.VITE_API_BASE_URL` or `window.API_BASE_URL`.
* Defaults to `${window.location.origin}/api` when served via FastAPI backend (`http://127.0.0.1:8000/dashboard`).

### How to Serve via Backend

```powershell
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

* **Dashboard URL**: `http://127.0.0.1:8000/dashboard` or `http://127.0.0.1:8000/`
* **Swagger Docs**: `http://127.0.0.1:8000/docs`
