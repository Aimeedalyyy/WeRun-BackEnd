from datetime import datetime, date, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model

from api.utils import (
    calculate_cycle_phase,
    get_phase_recommendations,
    get_user_cycle_context,
    get_cycle_day_for_date,
    mark_expired_sessions,
)
from api.models import Cycle, PrescribedSession

User = get_user_model()


class TestCalculateCyclePhase(TestCase):
    """Tests for calculate_cycle_phase utility function."""

    def setUp(self):
        self.base_date = datetime(2024, 1, 1)

    def _phase(self, days_offset):
        current = datetime(2024, 1, 1) + timedelta(days=days_offset)
        return calculate_cycle_phase(self.base_date, current)

    # --- Phase boundaries ---

    def test_menstruation_day_1(self):
        result = self._phase(0)
        self.assertEqual(result['phase'], 'Menstruation')
        self.assertEqual(result['cycle_day'], 1)
        self.assertEqual(result['days_until_next_phase'], 5)

    def test_menstruation_day_3(self):
        result = self._phase(2)
        self.assertEqual(result['phase'], 'Menstruation')
        self.assertEqual(result['cycle_day'], 3)

    def test_menstruation_day_5(self):
        result = self._phase(4)
        self.assertEqual(result['phase'], 'Menstruation')
        self.assertEqual(result['cycle_day'], 5)
        self.assertEqual(result['days_until_next_phase'], 1)

    def test_follicular_starts_at_day_6(self):
        result = self._phase(5)
        self.assertEqual(result['phase'], 'Follicular')
        self.assertEqual(result['cycle_day'], 6)
        self.assertEqual(result['days_until_next_phase'], 8)

    def test_follicular_day_13(self):
        result = self._phase(12)
        self.assertEqual(result['phase'], 'Follicular')
        self.assertEqual(result['cycle_day'], 13)
        self.assertEqual(result['days_until_next_phase'], 1)

    def test_ovulatory_starts_at_day_14(self):
        result = self._phase(13)
        self.assertEqual(result['phase'], 'Ovulatory')
        self.assertEqual(result['cycle_day'], 14)
        self.assertEqual(result['days_until_next_phase'], 3)

    def test_ovulatory_day_16(self):
        result = self._phase(15)
        self.assertEqual(result['phase'], 'Ovulatory')
        self.assertEqual(result['cycle_day'], 16)
        self.assertEqual(result['days_until_next_phase'], 1)

    def test_luteal_starts_at_day_17(self):
        result = self._phase(16)
        self.assertEqual(result['phase'], 'Luteal')
        self.assertEqual(result['cycle_day'], 17)

    def test_luteal_day_28(self):
        result = self._phase(27)
        self.assertEqual(result['phase'], 'Luteal')
        self.assertEqual(result['cycle_day'], 28)
        self.assertEqual(result['days_until_next_phase'], 1)

    # --- Cycle wrapping ---

    def test_cycle_wraps_day_29_becomes_day_1(self):
        result = self._phase(28)  # day 29 → wraps to 1
        self.assertEqual(result['cycle_day'], 1)
        self.assertEqual(result['phase'], 'Menstruation')

    def test_cycle_wraps_day_35_becomes_day_7(self):
        result = self._phase(34)  # day 35 → wraps to 7
        self.assertEqual(result['cycle_day'], 7)
        self.assertEqual(result['phase'], 'Follicular')

    # --- Return structure ---

    def test_returns_all_required_keys(self):
        result = self._phase(5)
        self.assertIn('phase', result)
        self.assertIn('cycle_day', result)
        self.assertIn('days_until_next_phase', result)
        self.assertIn('last_period_start', result)

    def test_last_period_start_is_isoformat(self):
        result = self._phase(0)
        # Should be parseable as ISO datetime
        parsed = datetime.fromisoformat(result['last_period_start'])
        self.assertEqual(parsed.date(), self.base_date.date())

    def test_defaults_to_today_when_no_current_date(self):
        result = calculate_cycle_phase(datetime(2020, 1, 1))
        self.assertIn('phase', result)
        self.assertIn('cycle_day', result)


class TestGetPhaseRecommendations(TestCase):
    """Tests for get_phase_recommendations utility function."""

    def test_menstrual_phase(self):
        result = get_phase_recommendations('Menstrual')
        self.assertIn('workout_intensity', result)
        self.assertIn('message', result)
        self.assertIn('activities', result)
        self.assertEqual(result['workout_intensity'], 'low-moderate')

    def test_follicular_phase(self):
        result = get_phase_recommendations('Follicular')
        self.assertEqual(result['workout_intensity'], 'moderate-high')
        self.assertIsInstance(result['activities'], list)

    def test_ovulatory_phase(self):
        result = get_phase_recommendations('Ovulatory')
        self.assertEqual(result['workout_intensity'], 'high')

    def test_luteal_phase(self):
        result = get_phase_recommendations('Luteal')
        self.assertEqual(result['workout_intensity'], 'moderate')

    def test_unknown_phase_returns_menstrual_fallback(self):
        result = get_phase_recommendations('Unknown')
        self.assertEqual(result['workout_intensity'], 'low-moderate')

    def test_activities_is_non_empty_list(self):
        for phase in ('Menstrual', 'Follicular', 'Ovulatory', 'Luteal'):
            result = get_phase_recommendations(phase)
            self.assertIsInstance(result['activities'], list)
            self.assertGreater(len(result['activities']), 0)


class TestGetUserCycleContext(TestCase):
    """Tests for get_user_cycle_context — requires DB."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='cycleuser', password='pass123'
        )

    def test_returns_none_tuple_when_no_cycle(self):
        phase, cycle_day = get_user_cycle_context(self.user, date(2024, 6, 1))
        self.assertIsNone(phase)
        self.assertIsNone(cycle_day)

    def test_returns_phase_and_day_with_cycle_data(self):
        Cycle.objects.create(
            user=self.user,
            period_start_date=date(2024, 6, 1),
        )
        phase, cycle_day = get_user_cycle_context(self.user, date(2024, 6, 1))
        self.assertEqual(phase, 'menstrual')
        self.assertEqual(cycle_day, 1)

    def test_phase_is_lowercased(self):
        Cycle.objects.create(
            user=self.user,
            period_start_date=date(2024, 6, 1),
        )
        phase, _ = get_user_cycle_context(self.user, date(2024, 6, 10))
        self.assertEqual(phase, phase.lower())

    def test_follicular_phase_detected(self):
        Cycle.objects.create(
            user=self.user,
            period_start_date=date(2024, 6, 1),
        )
        phase, cycle_day = get_user_cycle_context(self.user, date(2024, 6, 7))
        self.assertEqual(phase, 'follicular')
        self.assertEqual(cycle_day, 7)

    def test_uses_latest_cycle_when_multiple_exist(self):
        Cycle.objects.create(user=self.user, period_start_date=date(2024, 1, 1))
        Cycle.objects.create(user=self.user, period_start_date=date(2024, 6, 1))
        phase, cycle_day = get_user_cycle_context(self.user, date(2024, 6, 1))
        self.assertEqual(cycle_day, 1)  # day 1 of the latest cycle


class TestGetCycleDayForDate(TestCase):
    """Tests for get_cycle_day_for_date utility function."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='dayuser', password='pass123'
        )
        self.cycle = Cycle.objects.create(
            user=self.user,
            period_start_date=date(2024, 6, 1),
        )

    def test_returns_1_on_period_start(self):
        result = get_cycle_day_for_date(self.user, date(2024, 6, 1))
        self.assertEqual(result, 1)

    def test_returns_correct_day_midcycle(self):
        result = get_cycle_day_for_date(self.user, date(2024, 6, 15))
        self.assertEqual(result, 15)

    def test_returns_none_when_no_cycle(self):
        other_user = User.objects.create_user(username='nocy', password='p')
        result = get_cycle_day_for_date(other_user, date(2024, 6, 1))
        self.assertIsNone(result)

    def test_returns_none_before_period_start(self):
        result = get_cycle_day_for_date(self.user, date(2024, 5, 31))
        self.assertIsNone(result)

    def test_returns_none_after_period_end(self):
        self.cycle.period_end_date = date(2024, 6, 5)
        self.cycle.save()
        result = get_cycle_day_for_date(self.user, date(2024, 6, 10))
        self.assertIsNone(result)

    def test_returns_day_within_open_ended_cycle(self):
        # No period_end_date set — cycle is ongoing
        result = get_cycle_day_for_date(self.user, date(2024, 7, 1))
        self.assertEqual(result, 31)


class TestMarkExpiredSessions(TestCase):
    """Tests for mark_expired_sessions utility function."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='sessionuser', password='pass123'
        )
        self.cycle = Cycle.objects.create(
            user=self.user,
            period_start_date=date(2024, 1, 1),
        )

    def _make_session(self, prescribed_date, status='pending'):
        return PrescribedSession.objects.create(
            user=self.user,
            cycle=self.cycle,
            session_type='easy',
            cycle_phase='Follicular',
            prescribed_date=prescribed_date,
            distance=5.0,
            status=status,
        )

    def test_past_pending_sessions_become_skipped(self):
        session = self._make_session(date(2020, 1, 1))
        mark_expired_sessions(self.user)
        session.refresh_from_db()
        self.assertEqual(session.status, 'skipped')

    def test_future_pending_sessions_unchanged(self):
        session = self._make_session(date(2099, 1, 1))
        mark_expired_sessions(self.user)
        session.refresh_from_db()
        self.assertEqual(session.status, 'pending')

    def test_completed_sessions_not_changed_to_skipped(self):
        session = self._make_session(date(2020, 1, 1), status='completed')
        mark_expired_sessions(self.user)
        session.refresh_from_db()
        self.assertEqual(session.status, 'completed')

    def test_only_affects_the_given_user(self):
        other_user = User.objects.create_user(username='other', password='p')
        other_cycle = Cycle.objects.create(
            user=other_user, period_start_date=date(2024, 1, 1)
        )
        other_session = PrescribedSession.objects.create(
            user=other_user, cycle=other_cycle, session_type='easy',
            cycle_phase='Follicular', prescribed_date=date(2020, 1, 1),
            distance=5.0, status='pending',
        )
        mark_expired_sessions(self.user)
        other_session.refresh_from_db()
        self.assertEqual(other_session.status, 'pending')
