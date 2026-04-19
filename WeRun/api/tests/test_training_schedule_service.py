"""
Tests for api/services/training_schedule_service.py

Approach: behavioural + boundary.
Rather than asserting exact distances (which would over-specify the algorithm
and make tests brittle), these tests verify the *contracts* the service must
uphold regardless of exact numeric values:

  - A marathon plan produces longer long-run distances than a 5k plan.
  - Menstruation never receives a tempo session (PHASE_SESSION_CEILING).
  - Fun-mode defaults to a 12-week horizon when no race_date is given.
  - `adjust_todays_session_for_symptoms` downgrades at the correct burden
    thresholds (1.5 → rest, 0.8 → easy, 0.4 → reduce distance).
  - The schedule summary returns the correct shape.
  - Macro-phase distribution adds up to total_weeks.
"""

from datetime import date, timedelta

from django.test import TestCase
from django.contrib.auth import get_user_model

from api.models import (
    Cycle,
    RaceGoal,
    PrescribedSession,
    Symptom,
    SymptomLog,
)
from api.services.training_schedule_service import (
    generate_training_schedule,
    get_schedule_summary,
    adjust_todays_session_for_symptoms,
    _get_macro_phases,
    _get_macro_phase_for_week,
    _get_long_run_distance,
    _adjust_session_for_phase,
    RACE_CONFIG,
    PHASE_SESSION_CEILING,
    BURDEN_THRESHOLD_REST,
    BURDEN_THRESHOLD_EASY,
    BURDEN_THRESHOLD_REDUCE,
)

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_user(username):
    return User.objects.create_user(username=username, password="pass")


def _make_goal(user, race_type, weeks_ahead=16):
    """Creates a RaceGoal and a supporting Cycle for the user."""
    Cycle.objects.get_or_create(
        user=user,
        defaults={'period_start_date': date.today() - timedelta(days=7)},
    )
    race_date = None if race_type == 'fun' else date.today() + timedelta(weeks=weeks_ahead)
    return RaceGoal.objects.create(
        user=user,
        race_type=race_type,
        race_date=race_date,
        race_name='',
        is_active=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  _get_macro_phases — boundary tests
#  Ensures macro-block distribution always sums to total_weeks and
#  edge cases (very short plans) don't produce negative block sizes.
# ─────────────────────────────────────────────────────────────────────────────

class TestGetMacroPhases(TestCase):

    def test_blocks_sum_to_total_weeks(self):
        for total in [2, 4, 8, 12, 16, 24, 52]:
            with self.subTest(total_weeks=total):
                macro = _get_macro_phases(total)
                self.assertEqual(
                    sum(macro.values()), total,
                    msg=f"Blocks do not sum to {total}: {macro}"
                )

    def test_minimum_1_week_taper_always_enforced(self):
        for total in [1, 2, 3, 4]:
            macro = _get_macro_phases(total)
            self.assertGreaterEqual(macro['taper'], 1)

    def test_no_block_is_negative(self):
        for total in range(1, 10):
            macro = _get_macro_phases(total)
            for block, weeks in macro.items():
                self.assertGreaterEqual(weeks, 0, msg=f"{block} is negative for {total} weeks")

    def test_very_short_plan_2_weeks_gets_peak_and_taper(self):
        macro = _get_macro_phases(2)
        self.assertEqual(macro['taper'], 1)
        self.assertEqual(macro['peak'], 1)
        self.assertEqual(macro['base'], 0)
        self.assertEqual(macro['build'], 0)

    def test_16_week_plan_has_all_four_blocks(self):
        macro = _get_macro_phases(16)
        for block in ('base', 'build', 'peak', 'taper'):
            self.assertGreater(macro[block], 0, msg=f"Block '{block}' is 0 for 16-week plan")


class TestGetMacroPhaseForWeek(TestCase):

    def test_week_0_is_in_base_for_long_plan(self):
        macro = _get_macro_phases(16)
        self.assertEqual(_get_macro_phase_for_week(0, macro), 'base')

    def test_last_week_is_taper(self):
        macro = _get_macro_phases(16)
        self.assertEqual(_get_macro_phase_for_week(15, macro), 'taper')


# ─────────────────────────────────────────────────────────────────────────────
#  _get_long_run_distance — boundary tests
#  Long-run distance must start small and reach peak before tapering.
# ─────────────────────────────────────────────────────────────────────────────

class TestGetLongRunDistance(TestCase):

    def test_week_0_distance_is_less_than_peak(self):
        config = RACE_CONFIG['marathon']
        week0 = _get_long_run_distance(0, 16, config)
        self.assertLess(week0, config['peak_long_run_km'])

    def test_taper_distance_is_less_than_peak(self):
        config = RACE_CONFIG['marathon']
        total = 16
        # Last week is always in the taper block.
        taper_week = total - 1
        taper_km = _get_long_run_distance(taper_week, total, config)
        mid_km = _get_long_run_distance(total // 2, total, config)
        self.assertLess(taper_km, mid_km)

    def test_returns_positive_distance(self):
        for race_type, config in RACE_CONFIG.items():
            with self.subTest(race_type=race_type):
                km = _get_long_run_distance(0, 8, config)
                self.assertGreater(km, 0)


# ─────────────────────────────────────────────────────────────────────────────
#  _adjust_session_for_phase — phase ceiling enforcement
#  The ceiling prevents high-intensity sessions during low-energy phases.
# ─────────────────────────────────────────────────────────────────────────────

class TestAdjustSessionForPhase(TestCase):

    def test_rest_is_always_rest_regardless_of_phase(self):
        # Rest days must never be upgraded to a run — they are scheduled for
        # a reason (recovery, not a ceiling constraint).
        for phase in PHASE_SESSION_CEILING:
            self.assertEqual(_adjust_session_for_phase('rest', phase), 'rest')

    def test_tempo_not_allowed_during_menstruation(self):
        # Tempo is above the Menstruation ceiling — must be downgraded.
        result = _adjust_session_for_phase('tempo', 'Menstruation')
        self.assertIn(result, PHASE_SESSION_CEILING['Menstruation'])
        self.assertNotEqual(result, 'tempo')

    def test_tempo_allowed_during_follicular(self):
        # Follicular ceiling includes tempo — no downgrade expected.
        result = _adjust_session_for_phase('tempo', 'Follicular')
        self.assertEqual(result, 'tempo')

    def test_tempo_allowed_during_ovulatory(self):
        result = _adjust_session_for_phase('tempo', 'Ovulatory')
        self.assertEqual(result, 'tempo')

    def test_tempo_not_allowed_during_luteal(self):
        # Luteal ceiling is ['easy', 'moderate', 'long_run'] — tempo excluded.
        result = _adjust_session_for_phase('tempo', 'Luteal')
        self.assertNotEqual(result, 'tempo')
        self.assertIn(result, PHASE_SESSION_CEILING['Luteal'])

    def test_long_run_allowed_during_follicular(self):
        result = _adjust_session_for_phase('long_run', 'Follicular')
        self.assertEqual(result, 'long_run')

    def test_downgrade_falls_back_to_allowed_session(self):
        # Any downgrade must land on something in the allowed ceiling,
        # never on an arbitrary value.
        result = _adjust_session_for_phase('tempo', 'Menstruation')
        self.assertIn(result, PHASE_SESSION_CEILING['Menstruation'])


# ─────────────────────────────────────────────────────────────────────────────
#  generate_training_schedule — behavioural tests
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateTrainingSchedule(TestCase):

    def setUp(self):
        self.user = _make_user("scheduser")

    def test_creates_sessions_in_database(self):
        goal = _make_goal(self.user, '5k', weeks_ahead=8)
        generate_training_schedule(self.user, goal)

        count = PrescribedSession.objects.filter(user=self.user, race_goal=goal).count()
        self.assertGreater(count, 0)

    def test_all_created_sessions_are_pending(self):
        goal = _make_goal(self.user, '10k', weeks_ahead=8)
        sessions, _ = generate_training_schedule(self.user, goal)

        non_pending = [s for s in sessions if s.status != 'pending']
        self.assertEqual(len(non_pending), 0)

    def test_marathon_long_run_distances_exceed_5k_long_run_distances(self):
        # Marathon plan must have longer long runs than a 5k plan —
        # the core behavioural contract of the schedule generator.
        user_5k = _make_user("user5k")
        user_mara = _make_user("usermara")

        goal_5k = _make_goal(user_5k, '5k', weeks_ahead=16)
        goal_mara = _make_goal(user_mara, 'marathon', weeks_ahead=16)

        generate_training_schedule(user_5k, goal_5k)
        generate_training_schedule(user_mara, goal_mara)

        def max_long_run(u, g):
            return max(
                float(s.distance)
                for s in PrescribedSession.objects.filter(
                    user=u, race_goal=g, session_type='long_run'
                )
            )

        self.assertGreater(max_long_run(user_mara, goal_mara), max_long_run(user_5k, goal_5k))

    def test_no_tempo_sessions_during_menstruation(self):
        # Phase ceiling must be respected for every session in the schedule.
        user = _make_user("notempo")
        Cycle.objects.create(
            user=user, period_start_date=date.today() - timedelta(days=3)
        )
        goal = _make_goal(user, '10k', weeks_ahead=8)
        sessions, _ = generate_training_schedule(user, goal)

        menstrual_tempos = [
            s for s in sessions
            if s.cycle_phase == 'Menstruation' and s.session_type == 'tempo'
        ]
        self.assertEqual(len(menstrual_tempos), 0)

    def test_fun_mode_generates_12_weeks_of_sessions(self):
        # When race_type == 'fun' there is no race_date, so the service
        # defaults to a 12-week horizon.
        goal = _make_goal(self.user, 'fun')
        sessions, _ = generate_training_schedule(self.user, goal)

        # At 4 run days + 3 rest per week × 12 weeks → at least 48 sessions.
        # We check total > 0 and cover the expected horizon loosely.
        self.assertGreater(len(sessions), 0)
        if sessions:
            first = min(s.prescribed_date for s in sessions)
            last = max(s.prescribed_date for s in sessions)
            span_weeks = (last - first).days // 7
            self.assertGreaterEqual(span_weeks, 11)

    def test_returns_two_element_tuple(self):
        # Callers unpack (sessions, warnings) — the return shape must not change.
        goal = _make_goal(self.user, '5k', weeks_ahead=8)
        result = generate_training_schedule(self.user, goal)

        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_regenerating_schedule_clears_old_pending_sessions(self):
        # Creating a new race goal should reset the schedule, not stack on top.
        goal = _make_goal(self.user, '5k', weeks_ahead=8)
        generate_training_schedule(self.user, goal)
        first_count = PrescribedSession.objects.filter(
            user=self.user, race_goal=goal, status='pending'
        ).count()

        generate_training_schedule(self.user, goal)
        second_count = PrescribedSession.objects.filter(
            user=self.user, race_goal=goal, status='pending'
        ).count()

        # Count should be equal (regenerated), not doubled.
        self.assertEqual(first_count, second_count)

    def test_no_sessions_scheduled_after_race_date(self):
        goal = _make_goal(self.user, '10k', weeks_ahead=8)
        sessions, _ = generate_training_schedule(self.user, goal)

        late_sessions = [s for s in sessions if s.prescribed_date >= goal.race_date]
        self.assertEqual(len(late_sessions), 0)

    def test_half_marathon_peak_long_run_is_20km(self):
        # Hard-coded business rule from RACE_CONFIG — lock it in.
        self.assertEqual(RACE_CONFIG['half_marathon']['peak_long_run_km'], 20.0)

    def test_marathon_peak_long_run_is_32km(self):
        self.assertEqual(RACE_CONFIG['marathon']['peak_long_run_km'], 32.0)


# ─────────────────────────────────────────────────────────────────────────────
#  get_schedule_summary
# ─────────────────────────────────────────────────────────────────────────────

class TestGetScheduleSummary(TestCase):

    def setUp(self):
        self.user = _make_user("summuser")
        self.goal = _make_goal(self.user, '5k', weeks_ahead=8)
        self.sessions, self.warnings = generate_training_schedule(self.user, self.goal)

    def test_returns_none_when_no_sessions_exist(self):
        # If the schedule was wiped, summary must gracefully return None.
        PrescribedSession.objects.filter(user=self.user, race_goal=self.goal).delete()
        result = get_schedule_summary(self.user, self.goal)
        self.assertIsNone(result)

    def test_summary_has_required_keys(self):
        summary = get_schedule_summary(self.user, self.goal, self.warnings)

        for key in ('total_weeks', 'total_sessions', 'session_types',
                    'phase_breakdown', 'first_session', 'last_session',
                    'phase_warnings'):
            self.assertIn(key, summary, msg=f"Key '{key}' missing from summary")

    def test_total_sessions_matches_db_count(self):
        summary = get_schedule_summary(self.user, self.goal)
        db_count = PrescribedSession.objects.filter(
            user=self.user, race_goal=self.goal, status='pending'
        ).count()
        self.assertEqual(summary['total_sessions'], db_count)

    def test_phase_warnings_defaults_to_empty_list(self):
        summary = get_schedule_summary(self.user, self.goal)
        self.assertEqual(summary['phase_warnings'], [])

    def test_first_session_is_before_last_session(self):
        summary = get_schedule_summary(self.user, self.goal)
        self.assertLess(summary['first_session'], summary['last_session'])


# ─────────────────────────────────────────────────────────────────────────────
#  adjust_todays_session_for_symptoms — threshold boundary tests
#
#  Thresholds (from the service constants):
#    >= 1.5  → rest         (e.g. Cramps 1.0 + Fatigue 0.9 = 1.9)
#    >= 0.8  → easy + 60%   (e.g. Fatigue 0.9 alone)
#    >= 0.4  → same + 80%   (e.g. Headache 0.6 alone)
#    <  0.4  → no change    (e.g. Acne 0.1 alone)
# ─────────────────────────────────────────────────────────────────────────────

class TestAdjustTodaysSession(TestCase):

    def setUp(self):
        self.user = _make_user("adjustuser")
        self.cycle = Cycle.objects.create(
            user=self.user,
            period_start_date=date.today() - timedelta(days=7),
        )

    def _make_todays_session(self, session_type='tempo', distance=10.0):
        return PrescribedSession.objects.create(
            user=self.user,
            cycle=self.cycle,
            session_type=session_type,
            cycle_phase='Follicular',
            prescribed_date=date.today(),
            distance=distance,
            status='pending',
        )

    def _log_symptom(self, name):
        symptom, _ = Symptom.objects.get_or_create(name=name)
        SymptomLog.objects.get_or_create(
            user=self.user, symptom=symptom, date=date.today()
        )

    def test_returns_none_when_no_symptoms_logged(self):
        self._make_todays_session()
        result = adjust_todays_session_for_symptoms(self.user)
        self.assertIsNone(result)

    def test_returns_none_when_no_session_exists(self):
        # Symptoms logged but no session to adjust.
        self._log_symptom('Headache')
        result = adjust_todays_session_for_symptoms(self.user)
        self.assertIsNone(result)

    def test_severe_burden_downgrades_to_rest(self):
        # Cramps (1.0) + Fatigue (0.9) = 1.9 >= BURDEN_THRESHOLD_REST (1.5)
        session = self._make_todays_session(session_type='tempo', distance=10.0)
        self._log_symptom('Abdominal Cramps')
        self._log_symptom('Fatigue')

        adjust_todays_session_for_symptoms(self.user)
        session.refresh_from_db()

        self.assertEqual(session.session_type, 'rest')
        self.assertEqual(float(session.distance), 0.0)

    def test_moderate_burden_downgrades_to_easy_with_60_percent_distance(self):
        # Fatigue alone (0.9) >= BURDEN_THRESHOLD_EASY (0.8) but < REST threshold.
        session = self._make_todays_session(session_type='tempo', distance=10.0)
        self._log_symptom('Fatigue')

        adjust_todays_session_for_symptoms(self.user)
        session.refresh_from_db()

        self.assertEqual(session.session_type, 'easy')
        self.assertAlmostEqual(float(session.distance), 6.0, places=1)

    def test_mild_burden_reduces_distance_only(self):
        # Headache alone (0.6) >= BURDEN_THRESHOLD_REDUCE (0.4) but < EASY threshold.
        session = self._make_todays_session(session_type='tempo', distance=10.0)
        self._log_symptom('Headache')

        adjust_todays_session_for_symptoms(self.user)
        session.refresh_from_db()

        # Session type unchanged, distance reduced to 80%.
        self.assertEqual(session.session_type, 'tempo')
        self.assertAlmostEqual(float(session.distance), 8.0, places=1)

    def test_negligible_burden_makes_no_changes(self):
        # Acne alone (0.1) < BURDEN_THRESHOLD_REDUCE (0.4) — no adjustment.
        session = self._make_todays_session(session_type='tempo', distance=10.0)
        self._log_symptom('Acne')

        result = adjust_todays_session_for_symptoms(self.user)

        # Function returns None when no change is made.
        self.assertIsNone(result)
        session.refresh_from_db()
        self.assertEqual(session.session_type, 'tempo')
        self.assertAlmostEqual(float(session.distance), 10.0, places=1)

    def test_rest_sessions_are_not_adjusted(self):
        # There is no point downsgrading a rest day — leave it alone.
        session = self._make_todays_session(session_type='rest', distance=0.0)
        self._log_symptom('Abdominal Cramps')
        self._log_symptom('Fatigue')

        result = adjust_todays_session_for_symptoms(self.user)

        self.assertIsNone(result)
        session.refresh_from_db()
        self.assertEqual(session.session_type, 'rest')

    def test_burden_threshold_constants_have_correct_order(self):
        # Sanity-check the ordering of the thresholds so code relying on
        # elif chains doesn't accidentally skip or overlap a range.
        self.assertGreater(BURDEN_THRESHOLD_REST, BURDEN_THRESHOLD_EASY)
        self.assertGreater(BURDEN_THRESHOLD_EASY, BURDEN_THRESHOLD_REDUCE)
        self.assertGreater(BURDEN_THRESHOLD_REDUCE, 0)
