from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from api.models import (
    UserProfile,
    RunEntry,
    Trackable,
    UserTrackable,
    TrackableLog,
    Symptom,
    UserSymptom,
    SymptomLog,
    Cycle,
    CycleSampleLog,
    ActivePhase,
    PrescribedSession,
    RaceGoal,
    AdviceRule,
    DailyAdviceCache,
)

User = get_user_model()


class TestUserModel(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(username='alice', password='pass')
        self.assertEqual(user.username, 'alice')
        self.assertIsNone(user.affiliated_user)



class TestUserProfile(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='bob', password='pass')

    def test_create_profile(self):
        profile = UserProfile.objects.create(
            user=self.user,
            average_cycle_length=28,
        )
        self.assertEqual(profile.average_cycle_length, 28)
        self.assertEqual(str(profile), "bob's Profile")

    def test_default_cycle_length(self):
        profile = UserProfile.objects.create(user=self.user)
        self.assertEqual(profile.average_cycle_length, 28)


class TestRunEntry(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='runner', password='pass')

    def test_create_run_entry(self):
        from django.utils import timezone
        entry = RunEntry.objects.create(
            user=self.user,
            date=timezone.now(),
            pace=5.30,
            distance=5.0,
            motivation_level=7,
            exertion_level=6,
            cycle_phase='Follicular',
            cycle_id=1,
        )
        self.assertEqual(entry.cycle_phase, 'Follicular')
        self.assertEqual(entry.cycle_id, 1)
        self.assertFalse(entry.is_baseline)
        self.assertFalse(entry.is_prescribed)

    def test_str_representation(self):
        from django.utils import timezone
        entry = RunEntry.objects.create(
            user=self.user,
            date=timezone.now(),
            pace=5.00,
            distance=10.0,
            motivation_level=8,
            exertion_level=7,
            cycle_phase='Luteal',
            cycle_id=2,
        )
        self.assertIn('runner', str(entry))
        self.assertIn('Luteal', str(entry))

    def test_ordering_most_recent_first(self):
        from django.utils import timezone
        RunEntry.objects.create(
            user=self.user, date=timezone.now() - timedelta(days=2),
            pace=5.0, distance=5.0, motivation_level=5, exertion_level=5,
            cycle_phase='Menstruation', cycle_id=1,
        )
        RunEntry.objects.create(
            user=self.user, date=timezone.now(),
            pace=5.0, distance=5.0, motivation_level=5, exertion_level=5,
            cycle_phase='Follicular', cycle_id=1,
        )
        entries = RunEntry.objects.filter(user=self.user)
        self.assertEqual(entries[0].cycle_phase, 'Follicular')


class TestTrackable(TestCase):
    def test_create_trackable(self):
        t = Trackable.objects.create(name='Sleep', unit='hours')
        self.assertEqual(str(t), 'Sleep')

    def test_name_must_be_unique(self):
        Trackable.objects.create(name='Energy')
        with self.assertRaises(IntegrityError):
            Trackable.objects.create(name='Energy')


class TestUserTrackable(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tracker', password='pass')
        self.trackable = Trackable.objects.create(name='HeartRate', unit='bpm')

    def test_create_user_trackable(self):
        ut = UserTrackable.objects.create(user=self.user, trackable=self.trackable)
        self.assertIn('tracker', str(ut))
        self.assertIn('HeartRate', str(ut))

    def test_unique_together_prevents_duplicates(self):
        UserTrackable.objects.create(user=self.user, trackable=self.trackable)
        with self.assertRaises(IntegrityError):
            UserTrackable.objects.create(user=self.user, trackable=self.trackable)


class TestTrackableLog(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='loguser', password='pass')
        self.trackable = Trackable.objects.create(name='WaterIntake', unit='ml')

    def test_create_numeric_log(self):
        log = TrackableLog.objects.create(
            user=self.user,
            trackable=self.trackable,
            date=date.today(),
            value_numeric=2000,
        )
        self.assertEqual(log.value_numeric, 2000)

    def test_unique_together_user_trackable_date(self):
        TrackableLog.objects.create(
            user=self.user, trackable=self.trackable,
            date=date.today(), value_numeric=1500,
        )
        with self.assertRaises(IntegrityError):
            TrackableLog.objects.create(
                user=self.user, trackable=self.trackable,
                date=date.today(), value_numeric=2000,
            )


class TestSymptom(TestCase):
    def test_create_symptom(self):
        s = Symptom.objects.create(name='Cramps')
        self.assertEqual(str(s), 'Cramps')

    def test_name_is_unique(self):
        Symptom.objects.create(name='Fatigue')
        with self.assertRaises(IntegrityError):
            Symptom.objects.create(name='Fatigue')


class TestSymptomLog(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='symuser', password='pass')
        self.symptom = Symptom.objects.create(name='Headache')

    def test_create_symptom_log(self):
        log = SymptomLog.objects.create(
            user=self.user,
            symptom=self.symptom,
            date=date.today(),
            notes='Mild headache after run',
        )
        self.assertIn('Headache', str(log))

    def test_unique_together_user_symptom_date(self):
        SymptomLog.objects.create(
            user=self.user, symptom=self.symptom, date=date.today()
        )
        with self.assertRaises(IntegrityError):
            SymptomLog.objects.create(
                user=self.user, symptom=self.symptom, date=date.today()
            )


class TestCycle(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='cycler', password='pass')

    def test_create_cycle(self):
        cycle = Cycle.objects.create(
            user=self.user,
            period_start_date=date(2024, 6, 1),
        )
        self.assertIn('cycler', str(cycle))
        self.assertIn('2024-06-01', str(cycle))

    def test_period_end_is_optional(self):
        cycle = Cycle.objects.create(
            user=self.user,
            period_start_date=date(2024, 6, 1),
        )
        self.assertIsNone(cycle.period_end_date)


class TestCycleSampleLog(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='sampleuser', password='pass')
        self.cycle = Cycle.objects.create(
            user=self.user, period_start_date=date(2024, 6, 1)
        )

    def test_create_sample(self):
        sample = CycleSampleLog.objects.create(
            user=self.user,
            cycle=self.cycle,
            date_logged=date(2024, 6, 1),
            day_of_cycle=1,
            flow_type=2,
        )
        self.assertIn('sampleuser', str(sample))

    def test_attach_symptoms(self):
        symptom = Symptom.objects.create(name='Bloating')
        sample = CycleSampleLog.objects.create(
            user=self.user, cycle=self.cycle,
            date_logged=date(2024, 6, 1), day_of_cycle=1, flow_type=1,
        )
        sample.symptoms.add(symptom)
        self.assertIn(symptom, sample.symptoms.all())

    def test_unique_together_user_cycle_date(self):
        CycleSampleLog.objects.create(
            user=self.user, cycle=self.cycle,
            date_logged=date(2024, 6, 1), day_of_cycle=1, flow_type=1,
        )
        with self.assertRaises(IntegrityError):
            CycleSampleLog.objects.create(
                user=self.user, cycle=self.cycle,
                date_logged=date(2024, 6, 1), day_of_cycle=1, flow_type=2,
            )


class TestPrescribedSession(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='presuser', password='pass')
        self.cycle = Cycle.objects.create(
            user=self.user, period_start_date=date(2024, 6, 1)
        )

    def _make_session(self, prescribed_date):
        return PrescribedSession.objects.create(
            user=self.user,
            cycle=self.cycle,
            session_type='easy',
            cycle_phase='Follicular',
            prescribed_date=prescribed_date,
            distance=5.0,
        )

    def test_default_status_is_pending(self):
        session = self._make_session(date(2099, 1, 1))
        self.assertEqual(session.status, 'pending')

    def test_is_expired_past_date(self):
        session = self._make_session(date(2020, 1, 1))
        self.assertTrue(session.is_expired)

    def test_is_not_expired_future_date(self):
        session = self._make_session(date(2099, 1, 1))
        self.assertFalse(session.is_expired)

    def test_str_representation(self):
        session = self._make_session(date(2099, 1, 1))
        self.assertIn('presuser', str(session))
        self.assertIn('easy', str(session))
        self.assertIn('pending', str(session))


class TestRaceGoal(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='racer', password='pass')

    def test_create_race_goal(self):
        goal = RaceGoal.objects.create(
            user=self.user,
            race_type='5k',
            race_date=date(2025, 6, 1),
        )
        self.assertTrue(goal.is_active)
        self.assertIn('racer', str(goal))
        self.assertIn('5k', str(goal))

    def test_fun_mode_has_no_date(self):
        goal = RaceGoal.objects.create(
            user=self.user,
            race_type='fun',
        )
        self.assertIsNone(goal.race_date)
        self.assertIn('fun mode', str(goal))


class TestAdviceRule(TestCase):
    def test_create_rule(self):
        rule = AdviceRule.objects.create(
            phase='follicular',
            condition_type='none',
            advice_category='training',
            title='Push harder',
            advice_text='Great time to increase intensity.',
            priority=3,
        )
        self.assertIn('follicular', str(rule))
        self.assertIn('Push harder', str(rule))

    def test_ordering_by_priority(self):
        AdviceRule.objects.create(
            phase='follicular', condition_type='none', advice_category='training',
            title='Low prio', advice_text='...', priority=10,
        )
        AdviceRule.objects.create(
            phase='follicular', condition_type='none', advice_category='training',
            title='High prio', advice_text='...', priority=1,
        )
        rules = list(AdviceRule.objects.all())
        self.assertEqual(rules[0].title, 'High prio')


class TestDailyAdviceCache(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='cacheuser', password='pass')

    def test_create_cache(self):
        cache = DailyAdviceCache.objects.create(
            user=self.user,
            date=date.today(),
            advice=[{'title': 'Rest up', 'body': 'Take it easy today.'}],
        )
        self.assertIn('cacheuser', str(cache))

    def test_unique_together_user_date(self):
        DailyAdviceCache.objects.create(
            user=self.user, date=date.today(), advice=[]
        )
        with self.assertRaises(IntegrityError):
            DailyAdviceCache.objects.create(
                user=self.user, date=date.today(), advice=[]
            )
