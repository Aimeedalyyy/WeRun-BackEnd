"""
Tests for api/services/phase_service.py — tested in isolation from views.

Coverage targets:
  - initialise_active_phase
  - check_and_update_phase  (no-cycle, first-time, same-phase, phase-transition)
  - force_phase_reset
  - get_active_phase
  - _days_into_current_phase   (all four phase boundaries)
  - _prescribe_baseline_run    (creates session, deduplicates)
  - _invalidate_advice_cache
  - _fire_transition_events    (Ovulatory is intentionally excluded from baseline prescriptions)
"""

from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth import get_user_model

from api.models import ActivePhase, Cycle, PrescribedSession, DailyAdviceCache
from api.services.phase_service import (
    initialise_active_phase,
    check_and_update_phase,
    force_phase_reset,
    get_active_phase,
    _days_into_current_phase,
    _prescribe_baseline_run,
    _invalidate_advice_cache,
)

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
#  Shared fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _make_user(username="svcuser"):
    return User.objects.create_user(username=username, password="pass")


def _make_cycle(user, days_ago=7):
    """Creates a Cycle whose period started `days_ago` days in the past."""
    return Cycle.objects.create(
        user=user,
        period_start_date=date.today() - timedelta(days=days_ago),
    )


# ─────────────────────────────────────────────────────────────────────────────
#  _days_into_current_phase  — boundary tests
#  These mirror the hard boundaries in calculate_cycle_phase():
#    Menstruation days  1-5
#    Follicular         6-13
#    Ovulatory         14-16
#    Luteal            17-28
# ─────────────────────────────────────────────────────────────────────────────

class TestDaysIntoCurrentPhase(TestCase):

    def test_menstruation_day_1_is_day_0_into_phase(self):
        # Day 1 is the very first day of Menstruation — 0 days into it.
        self.assertEqual(_days_into_current_phase("Menstruation", 1), 0)

    def test_menstruation_day_5_is_day_4_into_phase(self):
        # Day 5 is the last day of Menstruation — 4 days in.
        self.assertEqual(_days_into_current_phase("Menstruation", 5), 4)

    def test_follicular_starts_at_day_6(self):
        # Day 6 is the first day of Follicular — 0 days into it.
        self.assertEqual(_days_into_current_phase("Follicular", 6), 0)

    def test_follicular_day_13_is_7_into_phase(self):
        # Day 13 is the last day of Follicular — 7 days in.
        self.assertEqual(_days_into_current_phase("Follicular", 13), 7)

    def test_ovulatory_starts_at_day_14(self):
        self.assertEqual(_days_into_current_phase("Ovulatory", 14), 0)

    def test_ovulatory_day_16_is_2_into_phase(self):
        self.assertEqual(_days_into_current_phase("Ovulatory", 16), 2)

    def test_luteal_starts_at_day_17(self):
        self.assertEqual(_days_into_current_phase("Luteal", 17), 0)

    def test_luteal_day_28_is_11_into_phase(self):
        # Day 28 is the last day of the cycle — 11 days into Luteal.
        self.assertEqual(_days_into_current_phase("Luteal", 28), 11)


# ─────────────────────────────────────────────────────────────────────────────
#  initialise_active_phase
# ─────────────────────────────────────────────────────────────────────────────

class TestInitialiseActivePhase(TestCase):

    def test_returns_none_when_user_has_no_cycle(self):
        # Without a Cycle record there is no period start to compute a phase from.
        user = _make_user("noinit")
        result = initialise_active_phase(user)
        self.assertIsNone(result)

    def test_creates_active_phase_record(self):
        user = _make_user("inituser")
        _make_cycle(user, days_ago=5)  # day 6 → Follicular

        active = initialise_active_phase(user)

        self.assertIsNotNone(active)
        self.assertIsInstance(active, ActivePhase)

    def test_active_phase_has_correct_user(self):
        user = _make_user("inituser2")
        _make_cycle(user, days_ago=3)  # day 4 → Menstruation

        active = initialise_active_phase(user)

        self.assertEqual(active.user, user)

    def test_calling_twice_does_not_create_duplicate(self):
        # update_or_create should be idempotent — one ActivePhase per user.
        user = _make_user("idempuser")
        _make_cycle(user, days_ago=5)

        initialise_active_phase(user)
        initialise_active_phase(user)

        self.assertEqual(ActivePhase.objects.filter(user=user).count(), 1)

    def test_phase_start_and_next_phase_dates_are_set(self):
        user = _make_user("datesuser")
        _make_cycle(user, days_ago=5)

        active = initialise_active_phase(user)

        self.assertIsNotNone(active.phase_start_date)
        self.assertIsNotNone(active.predicted_next_phase_date)
        # predicted next phase must be in the future
        self.assertGreater(active.predicted_next_phase_date, active.phase_start_date)


# ─────────────────────────────────────────────────────────────────────────────
#  check_and_update_phase  — happy path, edge cases, transitions
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckAndUpdatePhase(TestCase):

    def test_returns_none_false_when_no_cycle_exists(self):
        # A brand-new user with no period logged must not crash.
        user = _make_user("nocy")
        active, transitioned = check_and_update_phase(user)

        self.assertIsNone(active)
        self.assertFalse(transitioned)

    def test_first_call_creates_active_phase_and_signals_transition(self):
        # When no ActivePhase record exists yet, one should be initialised
        # and transitioned=True is returned so the caller knows it was fresh.
        user = _make_user("firstcall")
        _make_cycle(user, days_ago=5)

        active, transitioned = check_and_update_phase(user)

        self.assertIsNotNone(active)
        self.assertTrue(transitioned)
        self.assertTrue(ActivePhase.objects.filter(user=user).exists())

    def test_same_phase_on_consecutive_calls_does_not_signal_transition(self):
        # If the phase hasn't changed, transitioned must be False —
        # downstream side-effects (new sessions, cache clears) must not re-fire.
        user = _make_user("nophase")
        _make_cycle(user, days_ago=5)

        # First call seeds the ActivePhase.
        check_and_update_phase(user)
        # Second call within the same phase day.
        active, transitioned = check_and_update_phase(user)

        self.assertFalse(transitioned)

    def test_day_of_cycle_is_updated_on_same_phase_call(self):
        # Even without a phase transition, the stored day_of_cycle must
        # stay in sync with the current date.
        user = _make_user("dayupdate")
        _make_cycle(user, days_ago=6)  # day 7 → Follicular

        check_and_update_phase(user)
        active, _ = check_and_update_phase(user)

        self.assertEqual(active.day_of_cycle, 7)

    def test_phase_transition_detected_when_stored_phase_differs(self):
        # Manually seed an ActivePhase in 'Menstruation' but with a cycle
        # that is now day 7 (Follicular). The service must detect this mismatch.
        user = _make_user("phasechange")
        cycle = _make_cycle(user, days_ago=6)  # day 7 → Follicular

        # Plant a stale ActivePhase still showing Menstruation.
        ActivePhase.objects.create(
            user=user,
            cycle=cycle,
            phase='Menstruation',
            day_of_cycle=1,
            phase_start_date=date.today() - timedelta(days=6),
            predicted_next_phase_date=date.today(),
        )

        active, transitioned = check_and_update_phase(user)

        self.assertTrue(transitioned)
        self.assertEqual(active.phase, 'Follicular')

    def test_transition_updates_phase_start_date(self):
        user = _make_user("startdate")
        cycle = _make_cycle(user, days_ago=6)

        ActivePhase.objects.create(
            user=user, cycle=cycle, phase='Menstruation',
            day_of_cycle=1,
            phase_start_date=date.today() - timedelta(days=10),
            predicted_next_phase_date=date.today() - timedelta(days=5),
        )

        active, _ = check_and_update_phase(user)

        # After transition phase_start_date should reflect the new phase start,
        # not the old stale date.
        self.assertGreaterEqual(active.phase_start_date, date.today() - timedelta(days=6))


# ─────────────────────────────────────────────────────────────────────────────
#  force_phase_reset
# ─────────────────────────────────────────────────────────────────────────────

class TestForcePhaseReset(TestCase):

    def test_returns_none_when_no_cycle(self):
        user = _make_user("noreset")
        result = force_phase_reset(user)
        self.assertIsNone(result)

    def test_always_sets_phase_to_menstruation(self):
        user = _make_user("resetuser")
        _make_cycle(user, days_ago=20)  # would normally be Luteal

        active = force_phase_reset(user)

        self.assertEqual(active.phase, 'Menstruation')

    def test_always_sets_day_of_cycle_to_1(self):
        user = _make_user("dayoneuser")
        _make_cycle(user, days_ago=20)

        active = force_phase_reset(user)

        self.assertEqual(active.day_of_cycle, 1)

    def test_sets_phase_start_date_to_today(self):
        user = _make_user("todayuser")
        _make_cycle(user, days_ago=10)

        active = force_phase_reset(user)

        self.assertEqual(active.phase_start_date, date.today())

    def test_predicted_next_phase_is_5_days_ahead(self):
        # Menstruation lasts days 1-5, so next phase should be 5 days away.
        user = _make_user("nextphaseuser")
        _make_cycle(user, days_ago=10)

        active = force_phase_reset(user)

        self.assertEqual(
            active.predicted_next_phase_date,
            date.today() + timedelta(days=5)
        )

    def test_prescribes_baseline_run_on_reset(self):
        # Resetting to Menstruation should fire _fire_transition_events,
        # which prescribes a baseline 5k for Menstruation.
        user = _make_user("baselineuser")
        _make_cycle(user, days_ago=10)

        force_phase_reset(user)

        baseline = PrescribedSession.objects.filter(
            user=user, session_type='baseline_5k', cycle_phase='Menstruation'
        )
        self.assertTrue(baseline.exists())


# ─────────────────────────────────────────────────────────────────────────────
#  get_active_phase
# ─────────────────────────────────────────────────────────────────────────────

class TestGetActivePhase(TestCase):

    def test_returns_none_when_no_active_phase(self):
        user = _make_user("nophaseread")
        self.assertIsNone(get_active_phase(user))

    def test_returns_active_phase_when_it_exists(self):
        user = _make_user("hasphase")
        cycle = _make_cycle(user, days_ago=5)

        ActivePhase.objects.create(
            user=user, cycle=cycle, phase='Follicular',
            day_of_cycle=6,
            phase_start_date=date.today(),
            predicted_next_phase_date=date.today() + timedelta(days=7),
        )

        result = get_active_phase(user)

        self.assertIsNotNone(result)
        self.assertEqual(result.phase, 'Follicular')

    def test_does_not_modify_the_record(self):
        # get_active_phase is a pure read — the day_of_cycle must not change.
        user = _make_user("readonly")
        cycle = _make_cycle(user, days_ago=5)

        ActivePhase.objects.create(
            user=user, cycle=cycle, phase='Follicular',
            day_of_cycle=99,  # deliberately wrong value
            phase_start_date=date.today(),
            predicted_next_phase_date=date.today() + timedelta(days=7),
        )

        result = get_active_phase(user)

        # Read-only — should return whatever is stored, not recalculate.
        self.assertEqual(result.day_of_cycle, 99)


# ─────────────────────────────────────────────────────────────────────────────
#  _prescribe_baseline_run
# ─────────────────────────────────────────────────────────────────────────────

class TestPrescribeBaselineRun(TestCase):

    def setUp(self):
        self.user = _make_user("baseprescribe")
        self.cycle = _make_cycle(self.user, days_ago=3)

    def test_creates_pending_baseline_session(self):
        _prescribe_baseline_run(self.user, 'Follicular', self.cycle)

        session = PrescribedSession.objects.get(
            user=self.user, session_type='baseline_5k', cycle_phase='Follicular'
        )
        self.assertEqual(session.status, 'pending')
        self.assertEqual(float(session.distance), 5.0)

    def test_does_not_duplicate_if_called_twice(self):
        # Idempotency guard — phase transitions can fire multiple times
        # (e.g. app open during the same transition day).
        _prescribe_baseline_run(self.user, 'Follicular', self.cycle)
        _prescribe_baseline_run(self.user, 'Follicular', self.cycle)

        count = PrescribedSession.objects.filter(
            user=self.user, session_type='baseline_5k', cycle_phase='Follicular'
        ).count()
        self.assertEqual(count, 1)

    def test_different_phases_get_separate_sessions(self):
        # Each phase transition independently prescribes its own baseline.
        _prescribe_baseline_run(self.user, 'Menstruation', self.cycle)
        _prescribe_baseline_run(self.user, 'Follicular', self.cycle)

        count = PrescribedSession.objects.filter(
            user=self.user, session_type='baseline_5k'
        ).count()
        self.assertEqual(count, 2)


# ─────────────────────────────────────────────────────────────────────────────
#  _invalidate_advice_cache
# ─────────────────────────────────────────────────────────────────────────────

class TestInvalidateAdviceCache(TestCase):

    def setUp(self):
        self.user = _make_user("cacheuser")

    def test_deletes_todays_cache_entry(self):
        DailyAdviceCache.objects.create(
            user=self.user, date=date.today(), advice=[]
        )
        _invalidate_advice_cache(self.user)

        self.assertFalse(
            DailyAdviceCache.objects.filter(user=self.user, date=date.today()).exists()
        )

    def test_does_not_delete_past_cache_entries(self):
        # Only today's cache should be invalidated — historical records are
        # read-only audit data and should remain untouched.
        yesterday = date.today() - timedelta(days=1)
        DailyAdviceCache.objects.create(
            user=self.user, date=yesterday, advice=[]
        )

        _invalidate_advice_cache(self.user)

        self.assertTrue(
            DailyAdviceCache.objects.filter(user=self.user, date=yesterday).exists()
        )

    def test_no_error_when_cache_is_already_empty(self):
        # Calling invalidate when there is nothing to delete must be a no-op.
        try:
            _invalidate_advice_cache(self.user)
        except Exception as e:
            self.fail(f"_invalidate_advice_cache raised unexpectedly: {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  _fire_transition_events — Ovulatory is deliberately excluded from
#  baseline prescriptions because the phase is too short (3 days)
#  for a baseline run to be meaningful.
# ─────────────────────────────────────────────────────────────────────────────

class TestFireTransitionEventsBaselineRules(TestCase):
    """
    Verifies the intentional design choice: baseline runs are prescribed
    for Menstruation, Follicular, and Luteal but NOT Ovulatory.
    """

    def setUp(self):
        self.user = _make_user("fireuser")
        self.cycle = _make_cycle(self.user, days_ago=3)

    def _baseline_exists(self, phase):
        return PrescribedSession.objects.filter(
            user=self.user, session_type='baseline_5k', cycle_phase=phase
        ).exists()

    def test_menstruation_transition_prescribes_baseline(self):
        force_phase_reset(self.user)
        self.assertTrue(self._baseline_exists('Menstruation'))

    def test_ovulatory_transition_does_not_prescribe_baseline(self):
        # Seed an ActivePhase in Follicular so the service detects
        # a transition to Ovulatory when we manipulate the cycle date.
        cycle = Cycle.objects.create(
            user=self.user,
            period_start_date=date.today() - timedelta(days=13),
        )
        ActivePhase.objects.update_or_create(
            user=self.user,
            defaults={
                'cycle': cycle,
                'phase': 'Follicular',
                'day_of_cycle': 13,
                'phase_start_date': date.today() - timedelta(days=7),
                'predicted_next_phase_date': date.today(),
            }
        )
        # Trigger the check — cycle is now day 14 (Ovulatory).
        check_and_update_phase(self.user)

        self.assertFalse(self._baseline_exists('Ovulatory'))
