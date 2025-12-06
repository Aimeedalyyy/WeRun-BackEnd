from datetime import datetime, timedelta
from typing import Dict

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
        phase = "Menstrual"
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