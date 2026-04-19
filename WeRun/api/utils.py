from datetime import datetime, date, timezone
from typing import Dict
from .models import Cycle, PrescribedSession

def calculate_cycle_phase(last_period_start: datetime, current_date: datetime = None) -> Dict:
    """
    Calculate current cycle phase and day number.
    Returns: phase name, cycle day, days until next phase
    """
    if current_date is None:
        current_date = datetime.now()
    
    days_since_period = (current_date.date() - last_period_start.date()).days + 1
    
    # Handle cycles longer than 28 days (wrap around)
    cycle_day = ((days_since_period - 1) % 28) + 1
    
    if cycle_day <= 5:
        phase = "Menstruation"
        days_until_next = 6 - cycle_day
    elif cycle_day <= 13:
        phase = "Follicular"
        days_until_next = 14 - cycle_day
    elif cycle_day <= 16:
        phase = "Ovulatory"
        days_until_next = 17 - cycle_day
    else:
        phase = "Luteal"
        days_until_next = 29 - cycle_day
    
    return {
        "phase": phase,
        "cycle_day": cycle_day,
        "days_until_next_phase": days_until_next,
        "last_period_start": last_period_start.isoformat()
    }

def get_user_cycle_context(user, target_date: date):
    """
    Returns (phase_str, cycle_day_int) using the existing calculate_cycle_phase utility.
    Returns (None, None) if the user has no cycle data yet.
    """


    # ── Phase name mapping: your utils.py → advice engine ────────────────────
    PHASE_MAP = {
        "Menstruation": "menstrual",
        "Follicular":   "follicular",
        "Ovulatory":    "ovulatory",
        "Luteal":       "luteal",
    }

    latest_cycle = Cycle.objects.filter(user=user).order_by("-period_start_date").first()
    if not latest_cycle:
        return (None, None)

    try:
        last_period_dt = datetime.combine(latest_cycle.period_start_date, datetime.min.time())
        current_dt     = datetime.combine(target_date, datetime.min.time())
        phase_info     = calculate_cycle_phase(last_period_dt, current_dt)

        phase    = PHASE_MAP.get(phase_info["phase"])   # normalise to lowercase
        cycle_day = phase_info["cycle_day"]

        return (phase, cycle_day)

    except Exception:
        return (None, None)

def get_cycle_day_for_date(user, target_date: date) -> int | None:
    """
    Returns the cycle day (1-based) for a given date.
    Returns None if the date does not fall within any cycle.
    """

    cycle = (
        Cycle.objects
        .filter(
            user=user,
            period_start_date__lte=target_date
        )
        .order_by("-period_start_date")
        .first()
    )

    if not cycle:
        return None

    # If cycle has ended, make sure date is inside range
    if cycle.period_end_date and target_date > cycle.period_end_date:
        return None

    return (target_date - cycle.period_start_date).days + 1

def get_phase_recommendations(phase: str) -> Dict:
    """
    Get workout recommendations based on cycle phase.
    """
    recommendations = {
        "Menstrual": {
            "workout_intensity": "low-moderate",
            "message": "Focus on gentle movement and recovery. Listen to your body.",
            "activities": ["yoga", "walking", "light jogging"]
        },
        "Follicular": {
            "workout_intensity": "moderate-high",
            "message": "Great time for building strength and trying new challenges!",
            "activities": ["interval training", "strength training", "tempo runs"]
        },
        "Ovulatory": {
            "workout_intensity": "high",
            "message": "Peak performance time! Push for PRs and intense workouts.",
            "activities": ["speed work", "long runs", "HIIT"]
        },
        "Luteal": {
            "workout_intensity": "moderate",
            "message": "Maintain steady efforts. Prioritize consistency over intensity.",
            "activities": ["steady runs", "cross-training", "maintenance workouts"]
        }
    }
    return recommendations.get(phase, recommendations["Menstrual"])

def mark_expired_sessions(user):
    today = datetime.now()
    PrescribedSession.objects.filter(
        user=user,
        status='pending',
        prescribed_date__lt=today
    ).update(status='skipped')