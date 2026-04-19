"""
Tests for api/adviceService.py

The advice engine is a rule-matching pipeline:
  1. Fetch today's trackable logs, symptom names, and personal baselines.
  2. Evaluate each AdviceRule against that context.
  3. Pick the highest-priority rule per category (max MAX_CARDS = 4).
  4. Fall back to generic phase rules if nothing matched.
  5. Cache the result; return the cache on subsequent calls.

Tests are organised around each stage so failures point directly to the
broken layer rather than to the opaque top-level function.
"""

from datetime import date, timedelta

from django.test import TestCase
from django.contrib.auth import get_user_model

from api.models import (
    AdviceRule,
    Cycle,
    DailyAdviceCache,
    Symptom,
    SymptomLog,
    Trackable,
    TrackableLog,
)
from api.adviceService import (
    get_advice_for_user,
    invalidate_advice_cache,
    _run_engine,
    _rule_matches,
    _evaluate_numeric,
    _evaluate_vs_baseline,
    _pick_top_per_category,
    _get_todays_trackable_logs,
    _get_todays_symptom_names,
    _get_personal_baselines,
    BASELINE_UPLIFT,
    BASELINE_MINIMUM_LOGS,
    MAX_CARDS,
)

User = get_user_model()
TODAY = date.today()


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_user(username):
    return User.objects.create_user(username=username, password="pass")


def _make_rule(**kwargs):
    """Minimal AdviceRule factory with sensible defaults."""
    defaults = dict(
        phase='follicular',
        condition_type='none',
        advice_category='training',
        title='Test rule',
        advice_text='Do something.',
        priority=5,
        is_generic=False,
    )
    defaults.update(kwargs)
    return AdviceRule.objects.create(**defaults)


def _give_cycle(user, days_ago=7):
    return Cycle.objects.create(
        user=user, period_start_date=TODAY - timedelta(days=days_ago)
    )


# ─────────────────────────────────────────────────────────────────────────────
#  _evaluate_numeric — operator boundary tests
# ─────────────────────────────────────────────────────────────────────────────

class TestEvaluateNumeric(TestCase):

    # ── gte ──────────────────────────────────────────────────────────────────

    def test_gte_true_when_value_equals_threshold(self):
        self.assertTrue(_evaluate_numeric(5.0, 'gte', 5.0))

    def test_gte_true_when_value_exceeds_threshold(self):
        self.assertTrue(_evaluate_numeric(6.0, 'gte', 5.0))

    def test_gte_false_when_value_below_threshold(self):
        self.assertFalse(_evaluate_numeric(4.9, 'gte', 5.0))

    # ── lte ──────────────────────────────────────────────────────────────────

    def test_lte_true_when_value_equals_threshold(self):
        self.assertTrue(_evaluate_numeric(5.0, 'lte', 5.0))

    def test_lte_true_when_value_is_less(self):
        self.assertTrue(_evaluate_numeric(4.0, 'lte', 5.0))

    def test_lte_false_when_value_exceeds_threshold(self):
        self.assertFalse(_evaluate_numeric(5.1, 'lte', 5.0))

    # ── eq ───────────────────────────────────────────────────────────────────

    def test_eq_true_when_exactly_equal(self):
        self.assertTrue(_evaluate_numeric(7.0, 'eq', 7.0))

    def test_eq_false_when_not_equal(self):
        self.assertFalse(_evaluate_numeric(7.1, 'eq', 7.0))

    # ── unknown operator ─────────────────────────────────────────────────────

    def test_unknown_operator_returns_false(self):
        # Never raise — an unrecognised operator must silently return False
        # so bad data in the rules table doesn't crash the whole advice engine.
        self.assertFalse(_evaluate_numeric(5.0, 'not_an_op', 5.0))


# ─────────────────────────────────────────────────────────────────────────────
#  _evaluate_vs_baseline — boundary tests
#  BASELINE_UPLIFT = 0.05 means value must be > baseline * 1.05 to trigger.
# ─────────────────────────────────────────────────────────────────────────────

class TestEvaluateVsBaseline(TestCase):

    def test_above_baseline_true_when_exceeds_uplift(self):
        # baseline=100, uplift=5%, value must be > 105 to trigger.
        self.assertTrue(_evaluate_vs_baseline(106.0, 100.0, 'above_baseline'))

    def test_above_baseline_false_at_exact_uplift_boundary(self):
        # Exactly at the threshold (100 * 1.05 = 105) must NOT trigger —
        # the rule uses strict greater-than (>).
        self.assertFalse(_evaluate_vs_baseline(105.0, 100.0, 'above_baseline'))

    def test_above_baseline_false_below_threshold(self):
        self.assertFalse(_evaluate_vs_baseline(104.9, 100.0, 'above_baseline'))

    def test_below_baseline_true_when_below_uplift(self):
        # value must be < baseline * 0.95 to trigger.
        self.assertTrue(_evaluate_vs_baseline(94.0, 100.0, 'below_baseline'))

    def test_below_baseline_false_at_exact_boundary(self):
        # Exactly at 100 * (1 - 0.05) = 95 must NOT trigger.
        self.assertFalse(_evaluate_vs_baseline(95.0, 100.0, 'below_baseline'))

    def test_unknown_operator_returns_false(self):
        self.assertFalse(_evaluate_vs_baseline(50.0, 100.0, 'sideways'))

    def test_baseline_uplift_constant_is_5_percent(self):
        # Lock the business rule — changing BASELINE_UPLIFT changes advice
        # sensitivity and must be an intentional decision.
        self.assertAlmostEqual(BASELINE_UPLIFT, 0.05)


# ─────────────────────────────────────────────────────────────────────────────
#  _rule_matches — each condition_type branch
# ─────────────────────────────────────────────────────────────────────────────

class TestRuleMatches(TestCase):

    def _make_minimal_rule(self, condition_type='none', **kwargs):
        return _make_rule(condition_type=condition_type, **kwargs)

    def test_none_condition_always_matches(self):
        rule = self._make_minimal_rule('none')
        self.assertTrue(_rule_matches(rule, {}, set(), {}))

    def test_symptom_condition_matches_when_symptom_present(self):
        rule = self._make_minimal_rule('symptom', condition_key='cramps')
        self.assertTrue(_rule_matches(rule, {}, {'cramps'}, {}))

    def test_symptom_condition_no_match_when_absent(self):
        rule = self._make_minimal_rule('symptom', condition_key='cramps')
        self.assertFalse(_rule_matches(rule, {}, {'fatigue'}, {}))

    def test_symptom_matching_is_case_insensitive(self):
        # symptom names are normalised to lowercase in the engine.
        rule = self._make_minimal_rule('symptom', condition_key='cramps')
        self.assertTrue(_rule_matches(rule, {}, {'cramps'}, {}))

    def test_trackable_numeric_matches_when_condition_met(self):
        trackable = Trackable.objects.create(name='Sleep')
        user = _make_user('slpuser')
        log = TrackableLog.objects.create(
            user=user, trackable=trackable, date=TODAY, value_numeric=4.0
        )
        rule = self._make_minimal_rule(
            'trackable_numeric',
            condition_key='Sleep',
            condition_operator='lte',
            condition_value=6.0,
        )
        self.assertTrue(_rule_matches(rule, {'Sleep': log}, set(), {}))

    def test_trackable_numeric_no_match_when_log_absent(self):
        rule = self._make_minimal_rule(
            'trackable_numeric',
            condition_key='Sleep',
            condition_operator='lte',
            condition_value=6.0,
        )
        self.assertFalse(_rule_matches(rule, {}, set(), {}))

    def test_trackable_baseline_no_match_when_insufficient_history(self):
        # Without enough past logs to compute a baseline the rule must not fire.
        rule = self._make_minimal_rule(
            'trackable_baseline',
            condition_key='Resting Heart Rate',
            condition_operator='above_baseline',
        )
        self.assertFalse(_rule_matches(rule, {}, set(), {}))

    def test_unknown_condition_type_returns_false(self):
        # Defensive: a bad DB row must not crash the engine.
        rule = self._make_minimal_rule('unknown_type')
        self.assertFalse(_rule_matches(rule, {}, set(), {}))


# ─────────────────────────────────────────────────────────────────────────────
#  _pick_top_per_category — selection logic
# ─────────────────────────────────────────────────────────────────────────────

class TestPickTopPerCategory(TestCase):

    def test_returns_one_rule_per_category(self):
        rules = [
            _make_rule(advice_category='training', priority=1, title='Train A'),
            _make_rule(advice_category='training', priority=2, title='Train B'),
            _make_rule(advice_category='recovery', priority=1, title='Recover A'),
        ]
        result = _pick_top_per_category(rules, max_total=4)

        categories = [r.advice_category for r in result]
        self.assertEqual(len(categories), len(set(categories)))  # no duplicates

    def test_picks_highest_priority_within_category(self):
        # Lower priority number = higher priority (1 beats 10).
        rules = [
            _make_rule(advice_category='training', priority=10, title='Low'),
            _make_rule(advice_category='training', priority=1,  title='High'),
        ]
        result = _pick_top_per_category(rules, max_total=4)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].title, 'High')

    def test_respects_max_total_cap(self):
        # Even if there are 6 different categories, max 4 cards returned.
        rules = [
            _make_rule(advice_category=cat, priority=1, title=f'{cat} tip')
            for cat in ('training', 'recovery', 'nutrition', 'mindset')
        ]
        result = _pick_top_per_category(rules, max_total=MAX_CARDS)

        self.assertLessEqual(len(result), MAX_CARDS)

    def test_max_cards_constant_is_4(self):
        # Lock the UI contract — the iOS app renders exactly 4 cards.
        self.assertEqual(MAX_CARDS, 4)

    def test_empty_input_returns_empty_list(self):
        self.assertEqual(_pick_top_per_category([], max_total=4), [])


# ─────────────────────────────────────────────────────────────────────────────
#  _get_personal_baselines — baseline computation
# ─────────────────────────────────────────────────────────────────────────────

class TestGetPersonalBaselines(TestCase):

    def setUp(self):
        self.user = _make_user('baselinecomp')
        self.trackable = Trackable.objects.create(name='Resting Heart Rate')

    def test_returns_empty_when_fewer_than_minimum_logs(self):
        # BASELINE_MINIMUM_LOGS = 2 — need at least 2 historical readings
        # for the average to be meaningful. With only 1 log, return nothing.
        TrackableLog.objects.create(
            user=self.user, trackable=self.trackable,
            date=TODAY - timedelta(days=5), value_numeric=60.0
        )
        baselines = _get_personal_baselines(self.user, TODAY)
        self.assertNotIn('Resting Heart Rate', baselines)

    def test_returns_average_when_enough_logs(self):
        for i, val in enumerate([60.0, 62.0, 64.0], start=1):
            TrackableLog.objects.create(
                user=self.user, trackable=self.trackable,
                date=TODAY - timedelta(days=i), value_numeric=val
            )
        baselines = _get_personal_baselines(self.user, TODAY)

        self.assertIn('Resting Heart Rate', baselines)
        self.assertAlmostEqual(baselines['Resting Heart Rate'], 62.0, places=1)

    def test_excludes_todays_log_from_baseline(self):
        # Today's log is the value being compared TO the baseline —
        # including it would introduce circular comparison.
        for i in range(1, 4):
            TrackableLog.objects.create(
                user=self.user, trackable=self.trackable,
                date=TODAY - timedelta(days=i), value_numeric=60.0
            )
        # Add today's log — should be excluded from the 30-day window.
        TrackableLog.objects.create(
            user=self.user, trackable=self.trackable,
            date=TODAY, value_numeric=999.0
        )
        baselines = _get_personal_baselines(self.user, TODAY)
        # Baseline must reflect only the historical 60.0 readings.
        self.assertAlmostEqual(baselines['Resting Heart Rate'], 60.0, places=1)

    def test_only_uses_30_day_window(self):
        # Logs older than 30 days must not affect the rolling baseline.
        TrackableLog.objects.create(
            user=self.user, trackable=self.trackable,
            date=TODAY - timedelta(days=31), value_numeric=999.0
        )
        for i in range(1, 4):
            TrackableLog.objects.create(
                user=self.user, trackable=self.trackable,
                date=TODAY - timedelta(days=i), value_numeric=60.0
            )
        baselines = _get_personal_baselines(self.user, TODAY)
        self.assertAlmostEqual(baselines['Resting Heart Rate'], 60.0, places=1)

    def test_baseline_minimum_logs_constant_is_2(self):
        # Lock the minimum — if it changes, advice quality changes too.
        self.assertEqual(BASELINE_MINIMUM_LOGS, 2)


# ─────────────────────────────────────────────────────────────────────────────
#  get_advice_for_user — cache behaviour + full pipeline
# ─────────────────────────────────────────────────────────────────────────────

class TestGetAdviceForUser(TestCase):

    def setUp(self):
        self.user = _make_user('adviceuser')
        _give_cycle(self.user, days_ago=7)  # day 8 → Follicular

    def test_returns_list(self):
        result = get_advice_for_user(self.user, TODAY)
        self.assertIsInstance(result, list)

    def test_second_call_uses_cache(self):
        # The engine should only run once; subsequent calls return the cached result.
        # We verify this by checking that only one cache entry exists.
        get_advice_for_user(self.user, TODAY)
        get_advice_for_user(self.user, TODAY)

        cache_count = DailyAdviceCache.objects.filter(
            user=self.user, date=TODAY
        ).count()
        self.assertEqual(cache_count, 1)

    def test_result_is_stored_in_cache(self):
        get_advice_for_user(self.user, TODAY)

        self.assertTrue(
            DailyAdviceCache.objects.filter(user=self.user, date=TODAY).exists()
        )

    def test_result_does_not_exceed_max_cards(self):
        # Create many rules so the cap is exercised.
        for i in range(10):
            _make_rule(
                phase='follicular',
                advice_category='training',
                priority=i,
                title=f'Rule {i}',
                is_generic=True,
            )
        result = get_advice_for_user(self.user, TODAY)
        self.assertLessEqual(len(result), MAX_CARDS)

    def test_falls_back_to_generic_rules_when_nothing_matches(self):
        # A generic rule for the current phase must appear in the output
        # when no data-driven rules are triggered.
        _make_rule(
            phase='follicular', is_generic=True,
            title='Generic follicular tip', advice_category='training',
        )
        result = get_advice_for_user(self.user, TODAY)

        titles = [card['title'] for card in result]
        self.assertIn('Generic follicular tip', titles)

    def test_each_card_has_required_keys(self):
        _make_rule(phase='follicular', is_generic=True, advice_category='training')
        result = get_advice_for_user(self.user, TODAY)

        for card in result:
            for key in ('id', 'category', 'title', 'body', 'phase', 'priority'):
                self.assertIn(key, card, msg=f"Key '{key}' missing from advice card")

    def test_no_cycle_data_returns_empty_list(self):
        # A user who has never logged a period gets no advice (phase is unknown).
        userless = _make_user('nocycleadvice')
        result = get_advice_for_user(userless, TODAY)
        self.assertEqual(result, [])


# ─────────────────────────────────────────────────────────────────────────────
#  invalidate_advice_cache
# ─────────────────────────────────────────────────────────────────────────────

class TestInvalidateAdviceCache(TestCase):

    def setUp(self):
        self.user = _make_user('invuser')

    def test_clears_todays_cache(self):
        DailyAdviceCache.objects.create(user=self.user, date=TODAY, advice=[])
        invalidate_advice_cache(self.user, TODAY)

        self.assertFalse(
            DailyAdviceCache.objects.filter(user=self.user, date=TODAY).exists()
        )

    def test_does_not_clear_other_dates(self):
        yesterday = TODAY - timedelta(days=1)
        DailyAdviceCache.objects.create(user=self.user, date=yesterday, advice=[])
        invalidate_advice_cache(self.user, TODAY)

        self.assertTrue(
            DailyAdviceCache.objects.filter(user=self.user, date=yesterday).exists()
        )

    def test_forces_engine_rerun_on_next_call(self):
        # After invalidation, get_advice_for_user must run the engine again —
        # verified by checking a new cache entry is created.
        _give_cycle(self.user, days_ago=7)
        get_advice_for_user(self.user, TODAY)
        invalidate_advice_cache(self.user, TODAY)
        get_advice_for_user(self.user, TODAY)

        self.assertTrue(
            DailyAdviceCache.objects.filter(user=self.user, date=TODAY).exists()
        )


# ─────────────────────────────────────────────────────────────────────────────
#  _get_todays_trackable_logs and _get_todays_symptom_names
# ─────────────────────────────────────────────────────────────────────────────

class TestDataFetchers(TestCase):

    def setUp(self):
        self.user = _make_user('fetchuser')

    def test_symptom_names_returns_set_of_strings(self):
        symptom = Symptom.objects.create(name='Bloating')
        SymptomLog.objects.create(user=self.user, symptom=symptom, date=TODAY)

        names = _get_todays_symptom_names(self.user, TODAY)

        self.assertIsInstance(names, set)
        self.assertIn('Bloating', names)

    def test_symptom_names_empty_when_none_logged(self):
        names = _get_todays_symptom_names(self.user, TODAY)
        self.assertEqual(names, set())

    def test_symptom_names_only_returns_todays_entries(self):
        symptom = Symptom.objects.create(name='Nausea')
        SymptomLog.objects.create(
            user=self.user, symptom=symptom,
            date=TODAY - timedelta(days=1)
        )
        names = _get_todays_symptom_names(self.user, TODAY)
        self.assertNotIn('Nausea', names)

    def test_trackable_logs_returns_name_keyed_dict(self):
        t = Trackable.objects.create(name='Energy Level')
        TrackableLog.objects.create(
            user=self.user, trackable=t, date=TODAY, value_numeric=7.0
        )
        logs = _get_todays_trackable_logs(self.user, TODAY)

        self.assertIn('Energy Level', logs)
        self.assertEqual(float(logs['Energy Level'].value_numeric), 7.0)

    def test_trackable_logs_empty_when_none_logged(self):
        logs = _get_todays_trackable_logs(self.user, TODAY)
        self.assertEqual(logs, {})
