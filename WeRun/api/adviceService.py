"""
advice/services.py
Rule engine that evaluates AdviceRule records against a user's logged trackables, symptoms, and cycle context for a given date.
"""

from datetime import date, timedelta
from collections import defaultdict
from django.db.models import Q
from .models import AdviceRule, DailyAdviceCache, TrackableLog, SymptomLog      
from .utils import get_user_cycle_context  


BASELINE_UPLIFT   = 0.05
BASELINE_MINIMUM_LOGS = 2  # need at least this many past logs to compute a baseline
MAX_CARDS  = 4    



def get_advice_for_user(user, target_date: date = None) -> list[dict]:
    """
    Returns a list of up to MAX_CARDS advice card dicts for the user on target_date.
    Checks the DailyAdviceCache first — only runs the engine if no cached result exists.
    """
    if target_date is None:
        target_date = date.today()

    cached = DailyAdviceCache.objects.filter(user=user, date=target_date).first()
    if cached:
        print(f"\n🐞 Cache exists grabbing from the cache")
        return cached.advice

    print(f"\n🐞 Not in cache run the engine")
    advice_cards = _run_engine(user, target_date)
    

    DailyAdviceCache.objects.update_or_create(
        user=user,
        date=target_date,
        defaults={'advice': advice_cards}
    )

    return advice_cards


def invalidate_advice_cache(user, target_date: date = None):
    if target_date is None:
        target_date = date.today()
    DailyAdviceCache.objects.filter(user=user, date=target_date).delete()


# ─────────────────────────────────────────────────────────────────────────────
# Engine internals
# ─────────────────────────────────────────────────────────────────────────────

def _run_engine(user, target_date: date) -> list[dict]:
    print(f"\n=== Running Advice Engine for {user} on {target_date} ===")
    # 1. Cycle context
    phase, cycle_day = get_user_cycle_context(user, target_date)

    # 2. Today's data
    trackable_logs  = _get_todays_trackable_logs(user, target_date)
    symptom_names   = _get_todays_symptom_names(user, target_date)
    baselines       = _get_personal_baselines(user, target_date)

    # 3. Candidate rules — this phase + phase='any'
    candidates = AdviceRule.objects.filter(phase__in=[phase, 'any'])

    # Narrow by cycle day range if rule specifies one
    if cycle_day is not None:
        candidates = candidates.filter(
            Q(cycle_day_min__isnull=True) |
            Q(cycle_day_min__lte=cycle_day, cycle_day_max__gte=cycle_day)
        )

    # 4. Evaluate each rule
    matched = []
    for rule in candidates:
        if _rule_matches(rule, trackable_logs, symptom_names, baselines):
            print(f"- Rule matched '{rule}' (priority={rule.priority})")
            matched.append(rule)

    # 5. Pick top card per category, sorted by priority
    results = _pick_top_per_category(matched, max_total=MAX_CARDS)
    print(f"Selected top {len(results)} card(s) after "f"category/priority filtering (max={MAX_CARDS})")

    # 6. Fallback to generic phase advice if nothing matched
    if not results:
        results = list(
            AdviceRule.objects.filter(phase=phase, is_generic=True)
            .order_by('priority')[:MAX_CARDS]
        )
        print(f"    Generic fallback returned {len(results)} card(s)")

    print(f"=== Engine finished: returning {len(results)} card(s) ===\n")
    return [_serialise_rule(rule) for rule in results]


def _rule_matches(rule, trackable_logs: dict, symptom_names: set, baselines: dict) -> bool:
    ctype = rule.condition_type

    if ctype == 'none':
        return True

    if ctype == 'symptom':
        return rule.condition_key.lower() in symptom_names

    if ctype == 'trackable_numeric':
        log = trackable_logs.get(rule.condition_key)
        if log is None or log.value_numeric is None:
            return False
        return _evaluate_numeric(
            float(log.value_numeric),
            rule.condition_operator,
            rule.condition_value
        )

    if ctype == 'trackable_baseline':
        log = trackable_logs.get(rule.condition_key)
        baseline = baselines.get(rule.condition_key)
        if log is None or log.value_numeric is None or baseline is None:
            return False
        return _evaluate_vs_baseline(
            float(log.value_numeric),
            baseline,
            rule.condition_operator
        )

    return False


# ─────────────────────────────────────────────────────────────────────────────
# Data fetchers
# ─────────────────────────────────────────────────────────────────────────────

def _get_todays_trackable_logs(user, target_date: date) -> dict:
    """Returns {Trackable.name: TrackableLog} for today."""
    logs = (
        TrackableLog.objects
        .filter(user=user, date=target_date)
        .select_related('trackable')
    )
    return {log.trackable.name: log for log in logs}


def _get_todays_symptom_names(user, target_date: date) -> set:
    """Returns a set of symptom name strings logged today."""
    return set(
        SymptomLog.objects
        .filter(user=user, date=target_date)
        .values_list('symptom__name', flat=True)
    )


def _get_personal_baselines(user, target_date: date) -> dict:
    """
    Computes a 30-day rolling average per numeric trackable.
    Only included if >= BASELINE_MINIMUM_LOGS data points exist.
    Used for Resting Heart Rate and Body Temperature rules.
    """
    thirty_days_ago = target_date - timedelta(days=30)
    logs = (
        TrackableLog.objects
        .filter(
            user=user,
            date__gte=thirty_days_ago,
            date__lt=target_date,
            value_numeric__isnull=False
        )
        .select_related('trackable')
    )

    grouped = defaultdict(list)
    for log in logs:
        grouped[log.trackable.name].append(float(log.value_numeric))

    return {
        name: sum(values) / len(values)
        for name, values in grouped.items()
        if len(values) >= BASELINE_MINIMUM_LOGS
    }


# ─────────────────────────────────────────────────────────────────────────────
# Evaluators
# ─────────────────────────────────────────────────────────────────────────────

def _evaluate_numeric(value: float, operator: str, threshold: float) -> bool:
    if operator == 'gte': return value >= threshold
    if operator == 'lte': return value <= threshold
    if operator == 'eq':  return value == threshold
    return False


def _evaluate_vs_baseline(value: float, baseline: float, operator: str) -> bool:
    if operator == 'above_baseline':
        return value > baseline * (1 + BASELINE_UPLIFT)
    if operator == 'below_baseline':
        return value < baseline * (1 - BASELINE_UPLIFT)
    return False



def _pick_top_per_category(rules: list, max_total: int) -> list:
    """One card per advice category, highest priority first."""
    seen       = set()
    results    = []
    for rule in sorted(rules, key=lambda r: r.priority):
        if rule.advice_category not in seen:
            results.append(rule)
            seen.add(rule.advice_category)
        if len(results) == max_total:
            break
    return results


def _serialise_rule(rule) -> dict:
    """Converts an AdviceRule into the dict shape the iOS app receives."""
    return {
        'id':       str(rule.id),
        'category': rule.advice_category,  
        'title':    rule.title,
        'body':     rule.advice_text,
        'phase':    rule.phase,
        'priority': rule.priority,
    }