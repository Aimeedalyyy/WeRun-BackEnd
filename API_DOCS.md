# WeRun API Documentation

All protected endpoints require a JWT access token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

Tokens are obtained from `POST /auth/token/` and refreshed via `POST /auth/token/refresh/`.

Base URL: `http://localhost:8000`

---

## Table of Contents

1. [Authentication](#1-authentication)
   - [Register](#11-register)
   - [Obtain Token (Login)](#12-obtain-token-login)
   - [Refresh Token](#13-refresh-token)
2. [Diagnostics](#2-diagnostics)
   - [Test Endpoint](#21-test-endpoint)
3. [Run Logging](#3-run-logging)
   - [Log Run](#31-log-run)
4. [Health Tracking](#4-health-tracking)
   - [Log Trackable](#41-log-trackable)
   - [Log Symptom](#42-log-symptom)
   - [Get User Tracking Preferences](#43-get-user-tracking-preferences)
5. [Cycle Tracking](#5-cycle-tracking)
   - [Log Cycle Sample](#51-log-cycle-sample)
   - [Log Cycle Day](#52-log-cycle-day)
   - [User Dashboard](#53-user-dashboard)
   - [Cycle Calendar](#54-cycle-calendar)
6. [Advice](#6-advice)
   - [Today's Advice](#61-todays-advice)
   - [Phase Advice](#62-phase-advice)
7. [Training](#7-training)
   - [Active Phase](#71-active-phase)
   - [Prescribed Sessions](#72-prescribed-sessions)
   - [Complete Prescribed Session](#73-complete-prescribed-session)
8. [Race Goals](#8-race-goals)
   - [Get Race Goal](#81-get-race-goal)
   - [Create Race Goal](#82-create-race-goal)
9. [Analysis](#9-analysis)
   - [All Phases Comparison](#91-all-phases-comparison)
   - [Phase Comparison](#92-phase-comparison)

---

## 1. Authentication

---

### 1.1 Register

```
# -------------------------
# NAME:            Register
# FUNCTION:        Creates a new user account with selected trackables and symptoms
# METHOD:          POST
# ENDPOINT:        /api/register/
# AUTH:            None (public)
# URL/QUERY PARAMS: None
# -------------------------
```

**Request Body:**
```json
{
  "username": "sarah_collins",
  "password": "securepassword123",
  "email": "sarah@example.com",
  "trackables": ["Sleep", "Resting Heart Rate", "Hydration"],
  "symptoms": ["Abdominal Cramps", "Fatigue"]
}
```

**Response (201):**
```json
{
  "id": 1,
  "username": "sarah_collins",
  "email": "sarah@example.com"
}
```

**Error Responses:**

| Status | Reason |
|---|---|
| 400 | Username already taken, missing required fields, or invalid data |

---

### 1.2 Obtain Token (Login)

```
# -------------------------
# NAME:            Obtain JWT Token
# FUNCTION:        Authenticates a user and returns a JWT access + refresh token pair
# METHOD:          POST
# ENDPOINT:        /auth/token/
# AUTH:            None (public)
# URL/QUERY PARAMS: None
# -------------------------
```

**Request Body:**
```json
{
  "username": "sarah_collins",
  "password": "securepassword123"
}
```

**Response (200):**
```json
{
  "access": "<jwt_access_token>",
  "refresh": "<jwt_refresh_token>"
}
```

**Error Responses:**

| Status | Reason |
|---|---|
| 401 | Invalid credentials |

---

### 1.3 Refresh Token

```
# -------------------------
# NAME:            Refresh JWT Token
# FUNCTION:        Issues a new access token using a valid refresh token
# METHOD:          POST
# ENDPOINT:        /auth/token/refresh/
# AUTH:            None (public)
# URL/QUERY PARAMS: None
# -------------------------
```

**Request Body:**
```json
{
  "refresh": "<jwt_refresh_token>"
}
```

**Response (200):**
```json
{
  "access": "<new_jwt_access_token>"
}
```

**Error Responses:**

| Status | Reason |
|---|---|
| 401 | Refresh token expired or invalid |

---

## 2. Diagnostics

---

### 2.1 Test Endpoint

```
# -------------------------
# NAME:            Test Endpoint
# FUNCTION:        Validates API connectivity and tests cycle phase calculation
#                  given a last period start date. Useful for front-end smoke tests.
# METHOD:          POST
# ENDPOINT:        /api/test/
# AUTH:            None (public)
# URL/QUERY PARAMS: None
# -------------------------
```

**Request Body:**
```json
{
  "last_period_start": "2025-11-20T00:00:00Z"
}
```

**Response (200):**
```json
{
  "test_name": "API Connection Test",
  "test_number": 1,
  "current_date": "2025-12-03T10:00:00",
  "calculated_phase": "Follicular",
  "cycle_day": 14,
  "days_until_next_phase": 2
}
```

**Error Responses:**

| Status | Reason |
|---|---|
| 400 | `last_period_start` missing or not a valid ISO8601 datetime |
| 500 | Internal phase calculation error |

---

## 3. Run Logging

---

### 3.1 Log Run

```
# -------------------------
# NAME:            Log Run
# FUNCTION:        Records a completed run entry. Automatically calculates the
#                  menstrual cycle phase and cycle ID from the provided period start
#                  date and run date. Stores pace, distance, motivation and exertion.
# METHOD:          POST
# ENDPOINT:        /api/log-run/
# AUTH:            Required (JWT)
# URL/QUERY PARAMS: None
# -------------------------
```

**Request Body:**
```json
{
  "date": "2025-12-03T08:30:00Z",
  "pace": 5.45,
  "distance": 5.0,
  "motivation_level": 7,
  "exertion_level": 6,
  "last_period_start": "2025-11-20T00:00:00Z"
}
```

| Field | Type | Constraints |
|---|---|---|
| `date` | ISO8601 datetime | Must not be before `last_period_start` |
| `pace` | float | > 0 (minutes per km) |
| `distance` | float | > 0 (km) |
| `motivation_level` | integer | 1–10 |
| `exertion_level` | integer | 1–10 |
| `last_period_start` | ISO8601 datetime | Required for phase calculation |

**Response (201):**
```json
{
  "success": true,
  "entry_id": 42,
  "calculated_phase": "Follicular",
  "cycle_id": 3,
  "cycle_day": 14
}
```

**Error Responses:**

| Status | Reason |
|---|---|
| 400 | Missing fields, invalid date format, out-of-range numeric values, or run date before period start |
| 401 | Not authenticated |
| 500 | Phase or cycle ID calculation error |

---

## 4. Health Tracking

---

### 4.1 Log Trackable

```
# -------------------------
# NAME:            Log Trackable
# FUNCTION:        Records a daily health metric value (e.g. sleep hours, resting
#                  heart rate, hydration level) for the authenticated user.
#                  Saving a log automatically invalidates the advice cache for
#                  that date via a Django signal.
# METHOD:          POST
# ENDPOINT:        /api/log_trackables/
# AUTH:            Required (JWT)
# URL/QUERY PARAMS: None
# -------------------------
```

**Request Body:**
```json
{
  "trackable_name": "Sleep",
  "value": "7.5",
  "date": "2025-12-03"
}
```

| Field | Type | Notes |
|---|---|---|
| `trackable_name` | string | Must match a `Trackable` name in the database |
| `value` | string | Numeric or text depending on the trackable type |
| `date` | YYYY-MM-DD | Date the metric was recorded |

**Response (201):**
```json
{
  "id": 10,
  "trackable": "Sleep",
  "value": "7.5",
  "date": "2025-12-03"
}
```

**Error Responses:**

| Status | Reason |
|---|---|
| 400 | Invalid trackable name, missing fields, or duplicate entry for the same date |
| 401 | Not authenticated |

---

### 4.2 Log Symptom

```
# -------------------------
# NAME:            Log Symptom
# FUNCTION:        Records a symptom experienced by the user on a given date.
#                  Saving automatically invalidates the advice cache for that
#                  date via a Django signal.
# METHOD:          POST
# ENDPOINT:        /api/symptoms/
# AUTH:            Required (JWT)
# URL/QUERY PARAMS: None
# -------------------------
```

**Request Body:**
```json
{
  "symptom_name": "Abdominal Cramps",
  "date": "2025-12-03",
  "notes": "Quite painful in the morning"
}
```

| Field | Type | Notes |
|---|---|---|
| `symptom_name` | string | Must match a `Symptom` name in the database |
| `date` | YYYY-MM-DD | Date the symptom was experienced |
| `notes` | string | Optional free-text notes |

**Response (201):**
```json
{
  "id": 5,
  "symptom": "Abdominal Cramps",
  "date": "2025-12-03",
  "notes": "Quite painful in the morning"
}
```

**Error Responses:**

| Status | Reason |
|---|---|
| 400 | Invalid symptom name, missing fields, or duplicate entry for the same date |
| 401 | Not authenticated |

---

### 4.3 Get User Tracking Preferences

```
# -------------------------
# NAME:            User Tracking Preferences
# FUNCTION:        Returns the list of trackables and symptoms the authenticated
#                  user has selected to log. Used by the front-end to build
#                  the daily logging form.
# METHOD:          GET
# ENDPOINT:        /api/user_tracking/
# AUTH:            Required (JWT)
# URL/QUERY PARAMS: None
# -------------------------
```

**Response (200):**
```json
{
  "trackables": ["Sleep", "Resting Heart Rate", "Hydration"],
  "symptoms": ["Abdominal Cramps", "Fatigue", "Headache"]
}
```

**Error Responses:**

| Status | Reason |
|---|---|
| 401 | Not authenticated |

---

## 5. Cycle Tracking

---

### 5.1 Log Cycle Sample

```
# -------------------------
# NAME:            Log Cycle Sample
# FUNCTION:        Records a single daily cycle sample — flow type, day of cycle,
#                  and associated symptoms — linked to an existing Cycle record.
# METHOD:          POST
# ENDPOINT:        /api/cycles/
# AUTH:            Required (JWT)
# URL/QUERY PARAMS: None
# -------------------------
```

**Request Body:**
```json
{
  "cycle_id": "e017f0fa-cc03-42c1-92a7-a90b42d34f69",
  "date_logged": "2025-01-02",
  "day_of_cycle": 1,
  "flow_type": 1
}
```

| Field | Type | Notes |
|---|---|---|
| `cycle_id` | UUID | Must reference an existing `Cycle` belonging to the user |
| `date_logged` | YYYY-MM-DD | Date of this sample |
| `day_of_cycle` | integer | Day number within the cycle (starting at 1) |
| `flow_type` | integer | Flow intensity code (e.g. 1 = light, 2 = medium, 3 = heavy) |

**Response (201):**
```json
{
  "id": 12,
  "cycle": "e017f0fa-cc03-42c1-92a7-a90b42d34f69",
  "date_logged": "2025-01-02",
  "day_of_cycle": 1,
  "flow_type": 1
}
```

**Error Responses:**

| Status | Reason |
|---|---|
| 400 | Missing or invalid fields |
| 401 | Not authenticated |
| 404 | `cycle_id` not found or does not belong to the user |

---

### 5.2 Log Cycle Day

```
# -------------------------
# NAME:            Log Cycle Day
# FUNCTION:        Logs a cycle day with flow type, symptoms, and optional notes.
#                  Automatically calculates day_of_cycle from the cycle's period
#                  start date. Also creates or updates SymptomLog entries for each
#                  symptom provided.
# METHOD:          POST
# ENDPOINT:        /api/cycle-log/
# AUTH:            Required (JWT)
# URL/QUERY PARAMS: None
# -------------------------
```

**Request Body:**
```json
{
  "cycle_id": "e017f0fa-cc03-42c1-92a7-a90b42d34f69",
  "date_logged": "2025-01-03",
  "flow_type": 2,
  "symptoms": ["Abdominal Cramps", "Fatigue"],
  "notes": "Feeling tired today"
}
```

| Field | Type | Notes |
|---|---|---|
| `cycle_id` | UUID | Must reference an existing `Cycle` belonging to the user |
| `date_logged` | YYYY-MM-DD | Date of this cycle day |
| `flow_type` | integer | Flow intensity code |
| `symptoms` | array of strings | Names of symptoms experienced |
| `notes` | string | Optional free-text |

**Response (201):**
```json
{
  "id": 15,
  "cycle": "e017f0fa-cc03-42c1-92a7-a90b42d34f69",
  "date_logged": "2025-01-03",
  "day_of_cycle": 3,
  "flow_type": 2,
  "symptoms": ["Abdominal Cramps", "Fatigue"],
  "notes": "Feeling tired today"
}
```

**Error Responses:**

| Status | Reason |
|---|---|
| 400 | Missing or invalid fields |
| 401 | Not authenticated |
| 500 | `cycle_id` not found — **known bug**: view raises unhandled `DoesNotExist` instead of returning 404 |

---

### 5.3 User Dashboard

```
# -------------------------
# NAME:            User Tracking Dashboard
# FUNCTION:        Returns a full snapshot of the user's logged trackables,
#                  symptoms, and cycle history, along with the calculated current
#                  cycle phase based on the most recent logged cycle.
# METHOD:          GET
# ENDPOINT:        /api/user-info/
# AUTH:            Required (JWT)
# URL/QUERY PARAMS: None
# -------------------------
```

**Response (200):**
```json
{
  "trackables": [
    { "trackable": "Sleep", "value": "7.5", "date": "2025-12-03" }
  ],
  "symptoms": [
    { "symptom": "Fatigue", "date": "2025-12-03", "notes": "" }
  ],
  "cycles": [
    {
      "id": "e017f0fa-cc03-42c1-92a7-a90b42d34f69",
      "period_start_date": "2025-12-01",
      "samples": []
    }
  ],
  "current_cycle": {
    "calculated_phase": "Menstruation",
    "cycle_day": 3,
    "days_until_next_phase": 2,
    "last_period_start": "2025-12-01"
  }
}
```

**Error Responses:**

| Status | Reason |
|---|---|
| 401 | Not authenticated |

---

### 5.4 Cycle Calendar

```
# -------------------------
# NAME:            Cycle Calendar
# FUNCTION:        Returns a day-by-day breakdown of the predicted current cycle,
#                  including phase for each day and any prescribed training session
#                  scheduled for that date. Phase lengths are calculated from the
#                  user's own historical cycle and menstrual period averages.
# METHOD:          GET
# ENDPOINT:        /api/cycle-calendar/
# AUTH:            Required (JWT)
# URL/QUERY PARAMS: None
# -------------------------
```

**Response (200):**

Returns an array of objects — one per day of the predicted current cycle.

```json
[
  {
    "day_of_cycle": 1,
    "date": "2025-12-01",
    "phase": "menstruation",
    "workout": {
      "session_id": "3f1c...",
      "session_type": "rest",
      "distance": 0.0,
      "status": "pending"
    }
  },
  {
    "day_of_cycle": 6,
    "date": "2025-12-06",
    "phase": "follicular",
    "workout": null
  }
]
```

**Error Responses:**

| Status | Reason |
|---|---|
| 200 (empty array) | User has no logged cycles |
| 401 | Not authenticated |

---

## 6. Advice

---

### 6.1 Today's Advice

```
# -------------------------
# NAME:            Today's Advice
# FUNCTION:        Returns up to 4 personalised advice cards for the authenticated
#                  user based on their current cycle phase, logged symptoms, and
#                  trackable values compared against their personal 30-day baselines.
#                  Results are cached per user per date and automatically invalidated
#                  when new trackable or symptom data is logged.
#                  If no cycle has been logged, returns an empty advice list with
#                  a prompt to log a period.
# METHOD:          GET
# ENDPOINT:        /api/advice/today/
# AUTH:            Required (JWT)
# URL/QUERY PARAMS: ?date=YYYY-MM-DD  (optional — defaults to today)
# -------------------------
```

**Response (200) — with cycle data:**
```json
{
  "date": "2025-12-03",
  "phase": "follicular",
  "cycle_day": 8,
  "advice": [
    {
      "id": "uuid",
      "category": "training",
      "title": "Push harder today",
      "body": "Your energy is peaking in the follicular phase. This is a great time for higher-intensity sessions."
    }
  ]
}
```

**Response (200) — no cycle logged:**
```json
{
  "date": "2025-12-03",
  "phase": null,
  "cycle_day": null,
  "advice": [],
  "message": "Log your period to start receiving personalised advice."
}
```

**Error Responses:**

| Status | Reason |
|---|---|
| 400 | `date` query param is not a valid YYYY-MM-DD string |
| 401 | Not authenticated |

---

### 6.2 Phase Advice

```
# -------------------------
# NAME:            Phase Advice
# FUNCTION:        Returns all generic (non-personalised) advice rules for a given
#                  cycle phase. Useful for displaying phase guides or educational
#                  content regardless of the user's current logged data.
# METHOD:          GET
# ENDPOINT:        /api/advice/phase/<phase>/
# AUTH:            Required (JWT)
# URL/QUERY PARAMS: <phase> path param — one of: menstrual, follicular, ovulatory, luteal
# -------------------------
```

**Response (200):**
```json
{
  "phase": "follicular",
  "advice": [
    {
      "id": "uuid",
      "category": "training",
      "title": "Build your base",
      "body": "Rising oestrogen supports energy and recovery. Ideal phase for increasing training load."
    }
  ]
}
```

**Error Responses:**

| Status | Reason |
|---|---|
| 400 | Phase path param is not one of the four valid values |
| 401 | Not authenticated |

---

## 7. Training

---

### 7.1 Active Phase

```
# -------------------------
# NAME:            Active Phase
# FUNCTION:        Returns the user's current stored cycle phase and checks whether
#                  a phase transition has occurred since the last check. If a
#                  transition is detected, downstream events are fired exactly once:
#                  a baseline 5k session is prescribed, and the advice cache is
#                  invalidated. If no cycle has been logged, returns a prompt.
# METHOD:          GET
# ENDPOINT:        /api/active-phase/
# AUTH:            Required (JWT)
# URL/QUERY PARAMS: None
# -------------------------
```

**Response (200) — with cycle data:**
```json
{
  "phase": "Follicular",
  "day_of_cycle": 8,
  "phase_start_date": "2025-12-06",
  "predicted_next_phase_date": "2025-12-13",
  "phase_transitioned_today": false,
  "cycle_id": "e017f0fa-cc03-42c1-92a7-a90b42d34f69",
  "last_checked": "2025-12-03T09:00:00+00:00"
}
```

**Response (200) — no cycle logged:**
```json
{
  "phase": null,
  "message": "No cycle data found. Log your period to get started."
}
```

**Error Responses:**

| Status | Reason |
|---|---|
| 401 | Not authenticated |

---

### 7.2 Prescribed Sessions

```
# -------------------------
# NAME:            Prescribed Sessions
# FUNCTION:        Returns all prescribed training sessions for the authenticated
#                  user. Before returning, automatically marks any pending sessions
#                  whose prescribed date has passed as "skipped".
#                  Optionally filter by session status.
# METHOD:          GET
# ENDPOINT:        /api/prescribed-sessions/
# AUTH:            Required (JWT)
# URL/QUERY PARAMS: ?status=pending|completed|skipped  (optional)
# -------------------------
```

**Response (200):**
```json
{
  "count": 3,
  "sessions": [
    {
      "id": "uuid",
      "session_type": "baseline_5k",
      "cycle_phase": "Follicular",
      "prescribed_date": "2025-12-06",
      "distance": 5.0,
      "status": "pending",
      "is_expired": false,
      "cycle_id": "e017f0fa-cc03-42c1-92a7-a90b42d34f69",
      "completed_run_id": null
    }
  ]
}
```

**Session Types:**

| Type | Description |
|---|---|
| `baseline_5k` | Standardised 5 km effort to measure fitness per phase |
| `easy` | Low-intensity run |
| `moderate` | Moderate-intensity run |
| `tempo` | Higher-intensity threshold run |
| `long_run` | Weekly long run |
| `rest` | Rest day (no running) |

**Error Responses:**

| Status | Reason |
|---|---|
| 400 | `status` query param is not one of the three valid values |
| 401 | Not authenticated |

---

### 7.3 Complete Prescribed Session

```
# -------------------------
# NAME:            Complete Prescribed Session
# FUNCTION:        Marks a prescribed session as completed. Creates a linked RunEntry
#                  with the provided performance data. If the session type is
#                  "baseline_5k", the run is flagged as a baseline measurement for
#                  that cycle phase, which feeds into future advice and schedule
#                  generation.
# METHOD:          POST
# ENDPOINT:        /api/prescribed-sessions/complete/
# AUTH:            Required (JWT)
# URL/QUERY PARAMS: None
# -------------------------
```

**Request Body:**
```json
{
  "prescribed_session_id": "3f1c9b2e-...",
  "pace": 5.45,
  "distance": 5.0,
  "motivation_level": 7,
  "exertion_level": 6,
  "date": "2025-12-06T08:00:00Z"
}
```

| Field | Type | Constraints |
|---|---|---|
| `prescribed_session_id` | UUID | Must belong to the authenticated user |
| `pace` | float | > 0 (minutes per km) |
| `distance` | float | > 0 (km) |
| `motivation_level` | integer | 1–10 |
| `exertion_level` | integer | 1–10 |
| `date` | ISO8601 datetime | Date and time the run was completed |

**Response (201):**
```json
{
  "success": true,
  "run_entry_id": 88,
  "prescribed_session_id": "3f1c9b2e-...",
  "cycle_phase": "Follicular",
  "is_baseline": true,
  "baseline_phase": "Follicular"
}
```

**Error Responses:**

| Status | Reason |
|---|---|
| 400 | Missing fields, invalid numeric values, session already completed, or session type is `rest` |
| 401 | Not authenticated |
| 404 | `prescribed_session_id` not found or does not belong to the authenticated user |

---

## 8. Race Goals

---

### 8.1 Get Race Goal

```
# -------------------------
# NAME:            Get Race Goal
# FUNCTION:        Returns the user's currently active race goal. If no active goal
#                  exists, returns has_race_goal: false.
# METHOD:          GET
# ENDPOINT:        /api/race-goal/
# AUTH:            Required (JWT)
# URL/QUERY PARAMS: None
# -------------------------
```

**Response (200) — goal exists:**
```json
{
  "has_race_goal": true,
  "id": "uuid",
  "race_name": "Cork City Marathon",
  "race_type": "marathon",
  "race_date": "2025-10-19",
  "goal_time": "3:45:00",
  "is_active": true,
  "created_at": "2025-12-01T10:00:00+00:00"
}
```

**Response (200) — no active goal:**
```json
{
  "has_race_goal": false
}
```

**Error Responses:**

| Status | Reason |
|---|---|
| 401 | Not authenticated |

---

### 8.2 Create Race Goal

```
# -------------------------
# NAME:            Create Race Goal
# FUNCTION:        Creates a new race goal and deactivates any existing active goal.
#                  Immediately triggers full training schedule generation —
#                  creating PrescribedSession records from today to the race date,
#                  adjusted for the user's historical symptom burden per cycle phase.
#                  Fun mode does not require a race date.
# METHOD:          POST
# ENDPOINT:        /api/race-goal/
# AUTH:            Required (JWT)
# URL/QUERY PARAMS: None
# -------------------------
```

**Request Body:**
```json
{
  "race_type": "marathon",
  "race_date": "2025-10-19",
  "race_name": "Cork City Marathon",
  "goal_time": "03:45:00"
}
```

| Field | Type | Constraints |
|---|---|---|
| `race_type` | string | One of: `5k`, `10k`, `half_marathon`, `marathon`, `fun` |
| `race_date` | YYYY-MM-DD | Required for all types except `fun`. Must be in the future. |
| `race_name` | string | Optional free-text name for the race |
| `goal_time` | HH:MM:SS | Optional target finish time |

**Response (201):**
```json
{
  "success": true,
  "id": "uuid",
  "race_name": "Cork City Marathon",
  "race_type": "marathon",
  "race_date": "2025-10-19",
  "goal_time": "3:45:00",
  "is_active": true,
  "schedule": {
    "total_sessions": 120,
    "phases": { "base": 30, "build": 45, "peak": 30, "taper": 15 },
    "warnings": []
  }
}
```

**Response (201) — goal created but schedule generation failed:**
```json
{
  "success": true,
  "id": "uuid",
  "race_type": "marathon",
  "race_date": "2025-10-19",
  "schedule": null,
  "warning": "Race goal created but schedule generation failed: <detail>"
}
```

**Error Responses:**

| Status | Reason |
|---|---|
| 400 | Missing or invalid `race_type`, missing `race_date` for non-fun types, race date not in the future, or invalid `goal_time` format |
| 401 | Not authenticated |

---

## 9. Analysis

---

### 9.1 All Phases Comparison

```
# -------------------------
# NAME:            All Phases Comparison
# FUNCTION:        Compares running performance (average pace and motivation) across
#                  all four cycle phases between the user's most recent cycle and
#                  the previous one. Returns percentage change for each phase.
#                  Pace improvement is a decrease in value (lower = faster).
# METHOD:          GET
# ENDPOINT:        /api/all-phases-comparison/
# AUTH:            Required (JWT)
# URL/QUERY PARAMS: None
# -------------------------
```

**Response (200):**
```json
{
  "current_cycle": 3,
  "previous_cycle": 2,
  "phases": [
    {
      "phase": "Menstruation",
      "current_avg_pace": 6.10,
      "previous_avg_pace": 6.35,
      "current_avg_motivation": 5.2,
      "previous_avg_motivation": 4.8,
      "current_run_count": 4,
      "previous_run_count": 3,
      "pace_change_percent": -3.94,
      "motivation_change_percent": 8.33,
      "pace_improved": true,
      "has_comparison_data": true
    },
    {
      "phase": "Follicular",
      "current_avg_pace": null,
      "previous_avg_pace": null,
      "current_avg_motivation": null,
      "previous_avg_motivation": null,
      "current_run_count": 0,
      "previous_run_count": 0,
      "pace_change_percent": null,
      "motivation_change_percent": null,
      "pace_improved": null,
      "has_comparison_data": false
    }
  ]
}
```

**Error Responses:**

| Status | Reason |
|---|---|
| 401 | Not authenticated |
| 404 | User has no run entries |

---

### 9.2 Phase Comparison

```
# -------------------------
# NAME:            Phase Comparison
# FUNCTION:        Compares running performance for a single named cycle phase
#                  between the two most recent cycles recorded in CyclePhaseEntry.
#                  Returns average pace, average motivation, and percentage change.
#                  Note: this endpoint reads from the legacy CyclePhaseEntry model,
#                  not RunEntry. It is not fully tested and may return limited data
#                  for most users.
# METHOD:          GET
# ENDPOINT:        /api/phase-comparison/<phase_name>/
# AUTH:            None (public)
# URL/QUERY PARAMS: <phase_name> path param — one of: Menstrual, Follicular, Ovulatory, Luteal
# -------------------------
```

**Response (200):**
```json
{
  "phase": "Follicular",
  "current_cycle": 3,
  "previous_cycle": 2,
  "current_avg_pace": 5.80,
  "current_avg_motivation": 7.5,
  "pace_change_percent": -2.10,
  "motivation_change_percent": 5.00,
  "pace_improved": true
}
```

**Error Responses:**

| Status | Reason |
|---|---|
| 400 | `phase_name` is not one of the four valid values |
| 404 | No data found for this phase |
