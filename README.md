# WeRun — Backend API

A menstrual cycle-aware running training platform. The backend tracks runs, health metrics, and symptoms, then generates personalised training schedules and advice adjusted for each phase of the menstrual cycle.

Built with **Django REST Framework** and **PostgreSQL**, containerised with Docker.

[Backend Repo](https://github.com/Aimeedalyyy/WeRun-BackEnd)
[Frontend Repo](https://github.com/Aimeedalyyy/WeRun-FrontEnd)

---

## Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Models](#models)
- [API Endpoints](#api-endpoints)
- [Services](#services)
- [Getting Started](#getting-started)
- [Running Tests](#running-tests)

---

## Overview

WeRun correlates running performance with menstrual cycle phases across four phases — Menstruation, Follicular, Ovulatory, and Luteal — using a standard 28-day cycle model. The platform:

- Logs runs and computes which cycle phase they occurred in
- Tracks daily health metrics (sleep, heart rate, hydration, etc.) and symptoms (cramps, fatigue, headache, etc.)
- Generates full training schedules for a user's race goal, adjusted for hormonal patterns
- Provides personalised daily advice cards driven by a rule engine that compares current data against the user's personal baselines
- Automatically downgrades training sessions in real time based on logged symptoms

---

## Tech Stack

| Layer          | Technology                                           |
| -------------- | ---------------------------------------------------- |
| Framework      | Django 4.2, Django REST Framework                    |
| Authentication | JWT (`djangorestframework-simplejwt`) + Token Auth |
| Database       | PostgreSQL (development), SQLite in-memory (tests)   |
| Container      | Docker + Gunicorn                                    |
| Testing        | pytest, pytest-django, pytest-cov                    |

---

## Project Structure

```
WeRun/
├── WeRun/                  # Django project config (settings, urls, wsgi)
│   └── test_settings.py    # Overrides DB to SQLite for tests
├── api/
│   ├── models.py           # All database models
│   ├── views.py            # API view logic
│   ├── serializers.py      # DRF serializers
│   ├── urls.py             # URL routing
│   ├── utils.py            # Shared utility functions
│   ├── adviceService.py    # Advice rule engine
│   ├── signals.py          # Cache invalidation on model changes
│   ├── apps.py             # AppConfig — registers signals on startup
│   ├── services/
│   │   ├── phase_service.py             # Phase detection and transitions
│   │   └── training_schedule_service.py # Training schedule generation
│   ├── management/commands/
│   │   ├── seed_advice_rules.py         # Seeds the advice rule database
│   │   └── init_active_phases.py        # Initialises ActivePhase records
│   ├── migrations/
│   └── tests/
│       ├── test_models.py
│       ├── test_views.py
│       ├── test_utils.py
│       ├── test_auth.py
│       ├── test_advice_service.py
│       ├── test_phase_service.py
│       ├── test_training_schedule_service.py
│       └── test_fuzz.py
├── pytest.ini
├── .coveragerc
└── requirements.txt
```

---

## Models

| Model                 | Purpose                                                                        |
| --------------------- | ------------------------------------------------------------------------------ |
| `User`              | Extends `AbstractUser`; optional `affiliated_user` for coach relationships |
| `UserProfile`       | Stores average cycle length and period sync dates                              |
| `RunEntry`          | Individual run log with pace, distance, motivation, exertion, cycle phase      |
| `Trackable`         | Defines available health metrics (Sleep, Heart Rate, Hydration, etc.)          |
| `UserTrackable`     | Which trackables a user has opted to log                                       |
| `TrackableLog`      | Daily trackable value entry                                                    |
| `Symptom`           | Defines symptom types (Abdominal Cramps, Fatigue, Headache, etc.)              |
| `UserSymptom`       | Which symptoms a user is monitoring                                            |
| `SymptomLog`        | Daily symptom log entry                                                        |
| `Cycle`             | One menstrual cycle with start and optional end date                           |
| `CycleSampleLog`    | Daily sample logged during a cycle (flow type, day, symptoms)                  |
| `AdviceRule`        | Rule engine entry — conditions for when to show a specific advice card        |
| `DailyAdviceCache`  | Cached advice output per user per date                                         |
| `ActivePhase`       | Current cycle phase per user with transition tracking                          |
| `PrescribedSession` | A training session prescribed to the user (type, distance, date, status)       |
| `RaceGoal`          | User's active race goal (5k / 10k / half marathon / marathon / fun)            |

---

## API Endpoints

All protected endpoints require a JWT `Authorization: Bearer <token>` header.

### Authentication

| Method   | Endpoint                 | Description                        |
| -------- | ------------------------ | ---------------------------------- |
| `POST` | `/api/register/`       | Register a new user                |
| `POST` | `/auth/token/`         | Obtain JWT access + refresh tokens |
| `POST` | `/auth/token/refresh/` | Refresh an access token            |

### Run Logging

| Method   | Endpoint          | Description         |
| -------- | ----------------- | ------------------- |
| `POST` | `/api/log-run/` | Log a completed run |

### Health Tracking

| Method   | Endpoint                 | Description                                 |
| -------- | ------------------------ | ------------------------------------------- |
| `GET`  | `/api/user_tracking/`  | Get user's selected trackables and symptoms |
| `POST` | `/api/log_trackables/` | Log a daily health metric value             |
| `POST` | `/api/symptoms/`       | Log a symptom for a date                    |

### Cycle

| Method   | Endpoint                 | Description                                           |
| -------- | ------------------------ | ----------------------------------------------------- |
| `POST` | `/api/cycles/`         | Log cycle sample data                                 |
| `POST` | `/api/cycle-log/`      | Log a cycle day with symptoms                         |
| `GET`  | `/api/cycle-calendar/` | Retrieve cycle calendar with predicted phases         |
| `GET`  | `/api/user-info/`      | User dashboard — trackables, symptoms, cycle history |

### Advice

| Method  | Endpoint                       | Description                                                         |
| ------- | ------------------------------ | ------------------------------------------------------------------- |
| `GET` | `/api/advice/today/`         | Personalised advice cards for today (optional `?date=YYYY-MM-DD`) |
| `GET` | `/api/advice/phase/<phase>/` | Generic advice for a named phase                                    |

### Training & Race

| Method   | Endpoint                               | Description                                                      |
| -------- | -------------------------------------- | ---------------------------------------------------------------- |
| `GET`  | `/api/active-phase/`                 | Current cycle phase; checks for phase transitions                |
| `GET`  | `/api/prescribed-sessions/`          | List prescribed training sessions (optional `?status=` filter) |
| `POST` | `/api/prescribed-sessions/complete/` | Mark a session as completed                                      |
| `GET`  | `/api/race-goal/`                    | Get the active race goal                                         |
| `POST` | `/api/race-goal/`                    | Create a race goal and generate a training schedule              |

### Analysis

| Method  | Endpoint                                | Description                                           |
| ------- | --------------------------------------- | ----------------------------------------------------- |
| `GET` | `/api/all-phases-comparison/`         | Compare performance across all cycle phases           |
| `GET` | `/api/phase-comparison/<phase_name>/` | Compare current vs previous cycle stats for one phase |

---

## Services

### Phase Service (`api/services/phase_service.py`)

Detects phase transitions based on the current cycle day and fires downstream events exactly once per transition:

- Prescribes a baseline 5k run at the start of each phase (except Ovulatory — too short)
- Invalidates the advice cache so fresh advice is generated for the new phase

### Training Schedule Service (`api/services/training_schedule_service.py`)

Generates a full periodised training schedule (PrescribedSession records) from race goal to race date. Uses four adjustment layers:

1. **Predictive burden** — reduces distances in phases with a history of heavy symptoms
2. **Symptom weighting** — weights each symptom by its training impact (cramps = 1.0, acne = 0.1)
3. **Reactive adjustment** — downgrades today's session live based on symptoms logged today
4. **Phase warnings** — flags phases with a burden score ≥ 0.6

Phase intensity modifiers: Menstruation 0.70 × | Follicular 1.10 × | Ovulatory 1.15 × | Luteal 0.90 ×

### Advice Service (`api/adviceService.py`)

Rule-based engine that returns up to 4 personalised advice cards per day (one per category: training, recovery, nutrition, mindset). Rules are evaluated against:

- Current cycle phase
- Symptoms logged today
- Trackable values compared to the user's 30-day rolling baseline

Results are cached in `DailyAdviceCache` and automatically invalidated via Django signals when new trackable or symptom data is logged.

---

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development without Docker)

### With Docker

```bash
# Build and start the server + PostgreSQL database
docker-compose up --build

# Apply migrations (first run)
docker-compose exec web python manage.py migrate

# Seed advice rules
docker-compose exec web python manage.py seed_advice_rules

# Create an admin user
docker-compose exec web python manage.py createsuperuser
```

The API will be available at `http://localhost:8000`.

### Local Development (without Docker)

```bash
cd WeRun

# Install dependencies
pip install -r requirements.txt

# Apply migrations
python manage.py migrate

# Seed advice rules
python manage.py seed_advice_rules

# Start the development server
python manage.py runserver
```

### Management Commands

```bash
# Initialise ActivePhase records for all users who have cycle data
python manage.py init_active_phases

# Re-initialise for a specific user
python manage.py init_active_phases --username sarah_collins --force

# Seed the advice rule database
python manage.py seed_advice_rules
```

---

## Running Tests

Tests use an SQLite in-memory database — no Docker or PostgreSQL required.

```bash
cd WeRun

# Run the full test suite
python -m pytest api/tests/

# Run with coverage report
python -m pytest api/tests/ --cov=api --cov-report=term-missing

# Run a specific test file
python -m pytest api/tests/test_views.py

# Run a specific test class
python -m pytest api/tests/test_auth.py::TestJWTAuthentication -v
```

### Test Coverage

| File                                  | What is tested                                                                             |
| ------------------------------------- | ------------------------------------------------------------------------------------------ |
| `test_models.py`                    | Model creation,`__str__`, constraints, computed properties                               |
| `test_views.py`                     | Happy path for all API endpoints                                                           |
| `test_utils.py`                     | Cycle phase calculation, phase recommendations, cycle day lookup                           |
| `test_auth.py`                      | JWT auth, expired tokens, cross-user data isolation                                        |
| `test_advice_service.py`            | Rule matching, baseline evaluation, cache invalidation                                     |
| `test_phase_service.py`             | Phase detection, transition events, baseline session creation                              |
| `test_training_schedule_service.py` | Schedule generation, symptom adjustments, phase modifiers                                  |
| `test_fuzz.py`                      | Adversarial inputs at every endpoint (empty strings, SQL injection, XSS, oversized values) |
