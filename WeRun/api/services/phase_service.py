# =============================================================
#  api/services/phase_service.py
# =============================================================

from datetime import date, datetime, timedelta
from api.models import Cycle, ActivePhase


# ── Internal helpers ──────────────────────────────────────────

def _get_latest_cycle(user):
    return (
        Cycle.objects
        .filter(user=user)
        .order_by('-period_start_date')
        .first()
    )


def _compute_phase(user, target_date=None):
    """
    Fetches the user's latest cycle and calls calculate_cycle_phase()
    with the correct datetime arguments it expects.
    Returns (phase_info dict, cycle) or (None, None).
    """
    from api.utils import calculate_cycle_phase

    if target_date is None:
        target_date = date.today()

    latest_cycle = _get_latest_cycle(user)
    if not latest_cycle:
        return None, None

    # period_start_date is a date object — combine into datetime
    # as calculate_cycle_phase() expects datetime arguments
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

    phase_info = calculate_cycle_phase(last_period_dt, current_dt)
    return phase_info, latest_cycle


def _days_into_current_phase(phase, cycle_day):
    """
    Returns how many days into the current phase the user is,
    matching the boundaries in calculate_cycle_phase().
    """
    if phase == 'Menstruation':
        return cycle_day - 1
    elif phase == 'Follicular':
        return cycle_day - 6
    elif phase == 'Ovulatory':
        return cycle_day - 14
    else:  # Luteal
        return cycle_day - 17


def _phase_start_date(phase_info):
    days_into = _days_into_current_phase(
        phase_info['phase'],
        phase_info['cycle_day']
    )
    return date.today() - timedelta(days=days_into)


def _predicted_next_phase_date(phase_info):
    return date.today() + timedelta(days=phase_info['days_until_next_phase'])


# ── Public service functions ──────────────────────────────────

def initialise_active_phase(user):
    """
    Called once when a user logs their first period or registers.
    Creates the initial ActivePhase record.
    Returns the ActivePhase instance or None if no cycle data exists.
    """
    phase_info, latest_cycle = _compute_phase(user)
    if not phase_info or not latest_cycle:
        return None

    active_phase, created = ActivePhase.objects.update_or_create(
        user=user,
        defaults={
            'cycle':                     latest_cycle,
            'phase':                     phase_info['phase'],
            'day_of_cycle':              phase_info['cycle_day'],
            'phase_start_date':          _phase_start_date(phase_info),
            'predicted_next_phase_date': _predicted_next_phase_date(phase_info),
        }
    )
    return active_phase


def check_and_update_phase(user):
    """
    Call on every app open / dashboard load.
    Detects transitions and fires downstream events exactly once.
    Returns: (active_phase, transitioned: bool)
    """
    phase_info, latest_cycle = _compute_phase(user)
    if not phase_info or not latest_cycle:
        return None, False

    try:
        active = ActivePhase.objects.select_related('cycle').get(user=user)
    except ActivePhase.DoesNotExist:
        active = initialise_active_phase(user)
        if active:
            _fire_transition_events(user, None, active.phase, latest_cycle)
        return active, True

    # No transition — just keep day_of_cycle fresh
    if phase_info['phase'] == active.phase:
        active.day_of_cycle = phase_info['cycle_day']
        active.save(update_fields=['day_of_cycle', 'last_checked'])
        return active, False

    # ── Transition detected ───────────────────────────────────
    old_phase = active.phase
    new_phase = phase_info['phase']

    active.cycle                     = latest_cycle
    active.phase                     = new_phase
    active.day_of_cycle              = phase_info['cycle_day']
    active.phase_start_date          = _phase_start_date(phase_info)
    active.predicted_next_phase_date = _predicted_next_phase_date(phase_info)
    active.save()

    _fire_transition_events(user, old_phase, new_phase, latest_cycle)
    return active, True


def force_phase_reset(user):
    """
    Call immediately when a user logs a new period (day_of_cycle == 1).
    Resets phase to Menstruation without waiting for next app open.
    """
    latest_cycle = _get_latest_cycle(user)
    if not latest_cycle:
        return None

    active, _ = ActivePhase.objects.update_or_create(
        user=user,
        defaults={
            'cycle':                     latest_cycle,
            'phase':                     'Menstruation',
            'day_of_cycle':              1,
            'phase_start_date':          date.today(),
            'predicted_next_phase_date': date.today() + timedelta(days=5),
        }
    )

    _fire_transition_events(user, None, 'Menstruation', latest_cycle)
    return active


def get_active_phase(user):
    """
    Simple read — returns the stored ActivePhase for a user or None.
    Use anywhere you need the current phase without triggering an update.
    """
    try:
        return ActivePhase.objects.select_related('cycle').get(user=user)
    except ActivePhase.DoesNotExist:
        return None


# ── Transition event handlers ─────────────────────────────────

def _fire_transition_events(user, old_phase, new_phase, cycle):
    """
    Central hub for all phase-transition side effects.
    Fires exactly once per transition.
    """
    # 1. Prescribe baseline 5k (not for Ovulatory — phase is too short)
    if new_phase in ('Menstruation', 'Follicular', 'Luteal'):
        _prescribe_baseline_run(user, new_phase, cycle)

    # 2. Invalidate today's advice cache so it regenerates for new phase
    _invalidate_advice_cache(user)

    # 3. Log the transition
    _log_phase_transition(user, old_phase, new_phase, cycle)


def _prescribe_baseline_run(user, phase, cycle):
    """
    Creates a pending PrescribedSession for the baseline 5k.
    Skips if one already exists for this user/cycle/phase.
    """
    from api.models import PrescribedSession

    already_exists = PrescribedSession.objects.filter(
        user=user,
        cycle=cycle,
        cycle_phase=phase,
        session_type='baseline_5k',
    ).exists()

    if not already_exists:
        PrescribedSession.objects.create(
            user=user,
            cycle=cycle,
            session_type='baseline_5k',
            cycle_phase=phase,
            prescribed_date=date.today(),
            distance=5.0,
            status='pending',
        )


def _invalidate_advice_cache(user):
    from api.models import DailyAdviceCache
    DailyAdviceCache.objects.filter(user=user, date=date.today()).delete()


def _log_phase_transition(user, old_phase, new_phase, cycle):
    print(
        f"[PHASE TRANSITION] {user.username}: "
        f"{old_phase or 'init'} → {new_phase} "
        f"(cycle {cycle.id if cycle else 'unknown'}) "
        f"on {date.today()}"
    )