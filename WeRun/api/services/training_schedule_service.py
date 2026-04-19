# =============================================================
#  api/services/training_schedule_service.py
#
#  Generates a full training schedule as PrescribedSession
#  records when a user creates a RaceGoal.
#
#  Symptom data is used in four layers:
#    1. Predictive burden  — reduces distances in historically
#                            symptomatic phases at generation time
#    2. Symptom weighting  — weights symptoms by performance impact
#    3. Reactive adjustment — downgrades today's session if
#                             symptoms are logged on the day
#    4. Phase warnings     — flags problem phases in the response
#
# =============================================================

from datetime import date, datetime, timedelta
from api.models import Cycle, PrescribedSession


# =============================================================
#  CONFIG
# =============================================================

RACE_CONFIG = {
    '5k': {
        'peak_long_run_km': 8.0,
        'race_distance_km': 5.0,
    },
    '10k': {
        'peak_long_run_km': 14.0,
        'race_distance_km': 10.0,
    },
    'half_marathon': {
        'peak_long_run_km': 20.0, # runners world
        'race_distance_km': 21.1,
    },
    'marathon': {
        'peak_long_run_km': 32.0, # runners world
        'race_distance_km': 42.2,
    },
    'fun': {
        'peak_long_run_km': 10.0,
        'race_distance_km': None,
    },
}


PHASE_MODIFIERS = {
    'Menstruation': 0.70,   
    'Follicular':   1.10,  
    'Ovulatory':    1.15, 
    'Luteal':       0.90,  
}

PHASE_SESSION_CEILING = {
    'Menstruation': ['easy', 'rest'],
    'Follicular':   ['easy', 'moderate', 'tempo', 'long_run'],
    'Ovulatory':    ['easy', 'moderate', 'tempo', 'long_run'],
    'Luteal':       ['easy', 'moderate', 'long_run'],
}

SYMPTOM_WEIGHTS = {
    'Abdominal Cramps': 1.0,   # directly limits running
    'Fatigue':          0.9,
    'Lower Back Pain':  0.8,
    'Nausea':           0.8,
    'Diarrhoea':        0.7,
    'Headache':         0.6,
    'Chills':           0.5,
    'Bloating':         0.4,
    'Breast Pain':      0.3,
    'Acne':             0.1,   
}

BURDEN_THRESHOLD_REST     = 1.5   # downgrade to rest
BURDEN_THRESHOLD_EASY     = 0.8   # downgrade to easy + reduce distance
BURDEN_THRESHOLD_REDUCE   = 0.4   # reduce distance only

WEEKLY_TEMPLATE = [
    'easy',      # Monday
    'moderate',  # Tuesday
    'rest',      # Wednesday
    'tempo',     # Thursday
    'rest',      # Friday
    'long_run',  # Saturday
    'rest',      # Sunday
]


# =============================================================
#  Helper Functions
# =============================================================

def _get_macro_phases(total_weeks):
    if total_weeks <= 2:
        return {'base': 0, 'build': 0, 'peak': 1, 'taper': 1}

    taper = max(1, round(total_weeks * 0.10))
    peak  = max(1, round(total_weeks * 0.15))
    build = max(1, round(total_weeks * 0.35))
    base  = total_weeks - taper - peak - build

    return {
        'base':  max(base, 0),
        'build': max(build, 0),
        'peak':  max(peak, 0),
        'taper': taper,
    }


def _get_macro_phase_for_week(week_number, macro_phases):
    """Returns the macro phase label for a given week (0-indexed)."""
    base_end  = macro_phases['base']
    build_end = base_end  + macro_phases['build']
    peak_end  = build_end + macro_phases['peak']

    if week_number < base_end:
        return 'base'
    elif week_number < build_end:
        return 'build'
    elif week_number < peak_end:
        return 'peak'
    else:
        return 'taper'


def _get_long_run_distance(week_number, total_weeks, race_config):
    """
    Linear progression from 30% of peak up to peak distance,
    then tapers back down.
    """
    peak_km     = race_config['peak_long_run_km']
    start_km    = peak_km * 0.30
    macro       = _get_macro_phases(total_weeks)
    macro_phase = _get_macro_phase_for_week(week_number, macro)
    taper_start = total_weeks - macro['taper']

    if macro_phase == 'taper':
        taper_week = week_number - taper_start
        return round(peak_km * (0.70 - (taper_week * 0.15)), 1)

    progression_weeks = total_weeks - macro['taper']
    if progression_weeks == 0:
        return start_km

    progress = week_number / progression_weeks
    return round(max(start_km + (peak_km - start_km) * progress, start_km), 1)


def _get_session_distance(session_type, long_run_km, macro_phase):
    """Derives session distances relative to the week's long run."""
    ratios = {
        'base':  {'easy': 0.40, 'moderate': 0.55, 'tempo': 0.50, 'long_run': 1.00, 'rest': 0.0},
        'build': {'easy': 0.45, 'moderate': 0.60, 'tempo': 0.55, 'long_run': 1.00, 'rest': 0.0},
        'peak':  {'easy': 0.50, 'moderate': 0.65, 'tempo': 0.65, 'long_run': 1.00, 'rest': 0.0},
        'taper': {'easy': 0.35, 'moderate': 0.45, 'tempo': 0.40, 'long_run': 0.60, 'rest': 0.0},
    }
    ratio = ratios.get(macro_phase, ratios['base']).get(session_type, 0.5)
    return round(long_run_km * ratio, 1)


def _get_phase_for_date(user, target_date):
    """
    Returns the cycle phase string for a given date.
    Falls back to Follicular if no cycle data available.
    """
    from api.utils import calculate_cycle_phase

    latest_cycle = (
        Cycle.objects
        .filter(user=user)
        .order_by('-period_start_date')
        .first()
    )
    if not latest_cycle:
        return 'Follicular'

    last_period_dt = datetime.combine(
        latest_cycle.period_start_date
        if isinstance(latest_cycle.period_start_date, date)
        else latest_cycle.period_start_date.date(),
        datetime.min.time()
    )
    current_dt = datetime.combine(
        target_date
        if isinstance(target_date, date)
        else target_date.date(),
        datetime.min.time()
    )

    try:
        phase_info = calculate_cycle_phase(last_period_dt, current_dt)
        return phase_info['phase']
    except Exception:
        return 'Follicular'


def _adjust_session_for_phase(session_type, phase):
    """
    Downgrades session type if the phase ceiling doesn't allow it.
    """
    if session_type == 'rest':
        return 'rest'

    allowed = PHASE_SESSION_CEILING.get(phase, PHASE_SESSION_CEILING['Follicular'])
    if session_type in allowed:
        return session_type

    intensity_order = ['tempo', 'long_run', 'moderate', 'easy', 'rest']
    for fallback in intensity_order:
        if fallback in allowed:
            return fallback

    return 'rest'


# =============================================================
#  LAYER 1 + 2 — PREDICTIVE SYMPTOM BURDEN
#  Analyses historical symptom logs per phase to reduce
#  distances in phases the user consistently struggles with.
# =============================================================

def _get_historical_phase_dates(user, phase, cycles):
    """
    Returns a flat list of all historical dates that fell within
    the given phase across all logged cycles.
    Used to query SymptomLog for burden calculation.
    """
    from api.utils import calculate_cycle_phase

    phase_dates = []

    for cycle in cycles:
        start = cycle.period_start_date
        # Estimate cycle end — use next cycle start or +28 days
        next_cycle = (
            Cycle.objects
            .filter(user=user, period_start_date__gt=start)
            .order_by('period_start_date')
            .first()
        )
        end = next_cycle.period_start_date if next_cycle else start + timedelta(days=28)

        current = start
        while current < end:
            try:
                last_period_dt = datetime.combine(start, datetime.min.time())
                current_dt = datetime.combine(current, datetime.min.time())
                phase_info = calculate_cycle_phase(last_period_dt, current_dt)

                if phase_info['phase'] == phase:
                    phase_dates.append(current)
            except Exception:
                pass

            current += timedelta(days=1)

    return phase_dates


def _get_phase_symptom_burden(user, phase):
    """
    Layer 1 + 2 combined.
    Calculates a weighted symptom burden score for a phase
    based on all historical cycle data.

    Returns float 0.0 (no symptoms) → 1.0 (severe, max burden).
    """
    from api.models import SymptomLog

    cycles = Cycle.objects.filter(user=user).order_by('period_start_date')
    if cycles.count() < 2:
        # Not enough history to make a meaningful prediction
        return 0.0

    phase_dates = _get_historical_phase_dates(user, phase, cycles)
    if not phase_dates:
        return 0.0

    # Fetch all symptom logs on those dates
    symptom_logs = (
        SymptomLog.objects
        .filter(user=user, date__in=phase_dates)
        .select_related('symptom')
    )

    if not symptom_logs.exists():
        return 0.0

    # Layer 2 — weighted score instead of raw count
    total_weight = sum(
        SYMPTOM_WEIGHTS.get(log.symptom.name, 0.5)
        for log in symptom_logs
    )

    # Normalise: assume max 3.0 weighted symptoms per phase day = full burden
    days_in_phase = len(phase_dates)
    avg_weighted_per_day = total_weight / days_in_phase if days_in_phase > 0 else 0
    return round(min(avg_weighted_per_day / 3.0, 1.0), 3)


def _get_burden_distance_modifier(burden_score):
    """
    Converts a burden score into a distance reduction multiplier.
    Max reduction is 20% at full burden (score = 1.0).
    """
    return 1.0 - (burden_score * 0.20)





# =============================================================
#  MAIN SCHEDULE GENERATOR
# =============================================================

def generate_training_schedule(user, race_goal):
    print(f"\n=== Generating Training Schedule for {user} ===")
    print(f"Generating Training Schedule for Race goal: {race_goal.race_type} (race_date={race_goal.race_date})")
    start_date = date.today()
    race_date  = race_goal.race_date

    if not race_date or race_goal.race_type == 'fun':
        race_date = start_date + timedelta(weeks=12)

    total_days  = (race_date - start_date).days
    total_weeks = max(total_days // 7, 1)

    if total_weeks < 2:
        total_weeks = 2
    
    print(f"\n🐞Plan length: {total_weeks} week(s) from {start_date} to {race_date}")


    race_config  = RACE_CONFIG.get(race_goal.race_type, RACE_CONFIG['fun'])
    macro_phases = _get_macro_phases(total_weeks)


    burden_scores = {
        phase: _get_phase_symptom_burden(user, phase)
        for phase in ['Menstruation', 'Follicular', 'Ovulatory', 'Luteal']
    }
    print(f"\n🐞Symptom burden scores by phase: " f"{ {p: round(s, 2) for p, s in burden_scores.items()} }")


    # ── Clear existing pending sessions for this race goal ────
    PrescribedSession.objects.filter(
        user=user,
        race_goal=race_goal,
        status='pending',
        session_type__in=['easy', 'moderate', 'tempo', 'long_run', 'rest'],
    ).delete()

    latest_cycle = (
        Cycle.objects
        .filter(user=user)
        .order_by('-period_start_date')
        .first()
    )

    created_sessions = []
    current_date     = start_date

    for week_number in range(total_weeks):
        macro_phase = _get_macro_phase_for_week(week_number, macro_phases)
        long_run_km = _get_long_run_distance(week_number, total_weeks, race_config)
        print(f"\n--- Week {week_number + 1}/{total_weeks} " f"(macro='{macro_phase}', long_run_target={long_run_km}km) ---")

        for day_index, session_type in enumerate(WEEKLY_TEMPLATE):
            session_date = current_date + timedelta(days=day_index)

            if race_date and session_date >= race_date:
                print(f"Reached race date ({race_date}) -> stopping generation")
                break

            # Get phase for this date
            phase = _get_phase_for_date(user, session_date)

            # Adjust session type for phase ceiling
            adjusted_type = _adjust_session_for_phase(session_type, phase)
            if adjusted_type != session_type:
                print(f"  {session_date} [{phase}]: phase ceiling " f"downgraded '{session_type}' -> '{adjusted_type}'")

            # Base distance from macro phase ratios
            base_distance = _get_session_distance(adjusted_type, long_run_km, macro_phase)

            if base_distance > 0:
                phase_modifier  = PHASE_MODIFIERS.get(phase, 1.0)
                burden_modifier = _get_burden_distance_modifier(burden_scores.get(phase, 0.0))
                final_distance  = round(base_distance * phase_modifier * burden_modifier, 1)
                print(f"  {session_date} [{phase}] {adjusted_type}: " f"base={base_distance}km × phase_mod={phase_modifier} " f"× burden_mod={burden_modifier} -> {final_distance}km")
            else:
                final_distance = 0.0

            created_sessions.append(PrescribedSession(
                user=user,
                cycle=latest_cycle,
                race_goal=race_goal,
                session_type=adjusted_type,
                cycle_phase=phase,
                prescribed_date=session_date,
                distance=final_distance,
                status='pending',
            ))

        current_date += timedelta(weeks=1)

    PrescribedSession.objects.bulk_create(created_sessions)

    # Layer 4 — compute warnings after generation
    warnings = _get_phase_warnings(user)
    print(f"=== Schedule generation complete ===\n")
    return created_sessions, warnings


# =============================================================
#  LAYER 3 — REACTIVE SAME-DAY ADJUSTMENT
#  Call this on every app open alongside check_and_update_phase.
#  Downgrades today's session if symptoms have been logged today.
# =============================================================

def adjust_todays_session_for_symptoms(user):
    from api.models import SymptomLog

    today = date.today()

    todays_symptoms = (
        SymptomLog.objects
        .filter(user=user, date=today)
        .select_related('symptom')
    )

    if not todays_symptoms.exists():
        return None

    # Calculate today's weighted burden
    total_weight = sum(
        SYMPTOM_WEIGHTS.get(log.symptom.name, 0.5)
        for log in todays_symptoms
    )

    # Find today's pending session
    todays_session = PrescribedSession.objects.filter(
        user=user,
        prescribed_date=today,
        status='pending'
    ).first()

    if not todays_session or todays_session.session_type == 'rest':
        return None

    original_type     = todays_session.session_type
    original_distance = float(todays_session.distance)
    changed           = False

    if total_weight >= BURDEN_THRESHOLD_REST:
        todays_session.session_type = 'rest'
        todays_session.distance     = 0.0
        changed = True

    elif total_weight >= BURDEN_THRESHOLD_EASY:
        todays_session.session_type = 'easy'
        todays_session.distance     = round(original_distance * 0.6, 1)
        changed = True

    elif total_weight >= BURDEN_THRESHOLD_REDUCE:
        todays_session.distance = round(original_distance * 0.8, 1)
        changed = True

    if changed:
        todays_session.save(update_fields=['session_type', 'distance', 'updated_at'])
        print(
            f'[SYMPTOM ADJUSTMENT] {user.username}: '
            f'{original_type} {original_distance}km → '
            f'{todays_session.session_type} {todays_session.distance}km '
            f'(burden score: {round(total_weight, 2)})'
        )

    return todays_session if changed else None

# =============================================================
#  LAYER 4 — PHASE WARNINGS
#  Identifies phases with consistently high symptom burden
#  to surface in the API response.
# =============================================================

def _get_phase_warnings(user):
    """
    Returns warning messages for phases where the user
    consistently experiences high symptom burden.
    Only returned when burden >= 0.6.
    """
    warnings = []

    for phase in ['Menstruation', 'Follicular', 'Ovulatory', 'Luteal']:
        burden = _get_phase_symptom_burden(user, phase)

        if burden >= 0.6:
            warnings.append({
                'phase':   phase,
                'burden':  burden,
                'message': (
                    f'You typically experience significant symptoms during '
                    f'the {phase} phase. Training load for these days has '
                    f'been automatically reduced in your plan.'
                )
            })

    return warnings

# =============================================================
#  SCHEDULE SUMMARY
# =============================================================

def get_schedule_summary(user, race_goal, warnings=None):
    """
    Returns a human-readable breakdown of the generated schedule
    including phase warnings if provided.
    """
    sessions = PrescribedSession.objects.filter(
        user=user,
        race_goal=race_goal,
        status='pending',
    ).order_by('prescribed_date')

    if not sessions.exists():
        return None

    total_sessions = sessions.count()
    total_weeks    = (
        (sessions.last().prescribed_date - sessions.first().prescribed_date).days // 7
    )

    type_counts  = {}
    phase_counts = {}

    for s in sessions:
        type_counts[s.session_type] = type_counts.get(s.session_type, 0) + 1
        if s.session_type != 'rest':
            phase_counts[s.cycle_phase] = phase_counts.get(s.cycle_phase, 0) + 1

    return {
        'total_weeks':       total_weeks,
        'total_sessions':    total_sessions,
        'run_days_per_week': 4,
        'session_types':     type_counts,
        'phase_breakdown':   phase_counts,
        'first_session':     str(sessions.first().prescribed_date),
        'last_session':      str(sessions.last().prescribed_date),
        'phase_warnings':    warnings or [],
    }