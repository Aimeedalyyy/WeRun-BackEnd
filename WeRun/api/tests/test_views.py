from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework.authtoken.models import Token

from api.models import (
    Cycle,
    RunEntry,
    RaceGoal,
    PrescribedSession,
    Trackable,
    UserTrackable,
    Symptom,
    UserSymptom,
    AdviceRule,
)

User = get_user_model()


class BaseAPITestCase(TestCase):
    """Shared setup: creates a user and an authenticated client."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')


# ─────────────────────────────────────────────────────────────────────────────
#  /api/test/
# ─────────────────────────────────────────────────────────────────────────────

class TestEndpointView(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_valid_request_returns_phase_data(self):
        response = self.client.post('/api/test/', {
            'last_period_start': '2024-01-01T00:00:00Z'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('calculated_phase', response.data)
        self.assertIn('cycle_day', response.data)
        self.assertIn('days_until_next_phase', response.data)

    def test_missing_last_period_start_returns_400(self):
        response = self.client.post('/api/test/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_invalid_date_format_returns_400(self):
        response = self.client.post('/api/test/', {
            'last_period_start': 'not-a-date'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_response_contains_test_name(self):
        response = self.client.post('/api/test/', {
            'last_period_start': '2024-06-01T00:00:00Z'
        }, format='json')
        self.assertEqual(response.data['test_name'], 'API Connection Test')


# ─────────────────────────────────────────────────────────────────────────────
#  /api/analysis/
# ─────────────────────────────────────────────────────────────────────────────

class AnalysisEndpointView(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_returns_four_phases(self):
        response = self.client.get('/api/analysis/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 4)

    def test_each_phase_has_required_fields(self):
        response = self.client.get('/api/analysis/')
        for phase in response.data:
            self.assertIn('phase_name', phase)
            self.assertIn('avg_pace', phase)
            self.assertIn('motivation_level', phase)

    def test_phase_names_are_correct(self):
        response = self.client.get('/api/analysis/')
        names = [p['phase_name'] for p in response.data]
        self.assertIn('Menstrual', names)
        self.assertIn('Follicular', names)
        self.assertIn('Ovulatory', names)
        self.assertIn('Luteal', names)


# ─────────────────────────────────────────────────────────────────────────────
#  /api/register/
# ─────────────────────────────────────────────────────────────────────────────

class RegisterViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register_minimal_user(self):
        response = self.client.post('/api/register/', {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'securepass123',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_register_creates_user_profile(self):
        from api.models import UserProfile
        self.client.post('/api/register/', {
            'username': 'profileuser',
            'password': 'pass123',
            'average_cycle_length': 30,
        }, format='json')
        user = User.objects.get(username='profileuser')
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        self.assertEqual(user.userprofile.average_cycle_length, 30)

    def test_register_with_trackables(self):
        response = self.client.post('/api/register/', {
            'username': 'trackuser',
            'password': 'pass123',
            'trackables': [
                {'name': 'Sleep', 'value_numeric': 7.5},
                {'name': 'Energy Level'},
            ],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username='trackuser')
        self.assertEqual(user.trackables.count(), 2)

    def test_register_with_symptoms(self):
        response = self.client.post('/api/register/', {
            'username': 'symptomuser',
            'password': 'pass123',
            'symptoms': ['Cramps', 'Fatigue'],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username='symptomuser')
        self.assertEqual(user.symptoms.count(), 2)

    def test_duplicate_username_returns_400(self):
        User.objects.create_user(username='taken', password='pass')
        response = self.client.post('/api/register/', {
            'username': 'taken',
            'password': 'pass123',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────────────────────────────────────
#  /api/log-run/
# ─────────────────────────────────────────────────────────────────────────────

class LogRunViewTest(BaseAPITestCase):

    VALID_PAYLOAD = {
        'date': '2024-06-10T08:00:00Z',
        'pace': 5.30,
        'distance': 5.0,
        'motivation_level': 7,
        'exertion_level': 6,
        'last_period_start': '2024-06-01T00:00:00Z',
    }

    def test_valid_run_creates_entry(self):
        response = self.client.post('/api/log-run/', self.VALID_PAYLOAD, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
        self.assertIn('calculated_phase', response.data)

    def test_valid_run_stores_in_db(self):
        self.client.post('/api/log-run/', self.VALID_PAYLOAD, format='json')
        self.assertEqual(RunEntry.objects.filter(user=self.user).count(), 1)

    def test_missing_field_returns_400(self):
        payload = dict(self.VALID_PAYLOAD)
        del payload['pace']
        response = self.client.post('/api/log-run/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('missing_fields', response.data)
        self.assertIn('pace', response.data['missing_fields'])

    def test_invalid_date_format_returns_400(self):
        payload = {**self.VALID_PAYLOAD, 'date': 'not-a-date'}
        response = self.client.post('/api/log-run/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_period_date_format_returns_400(self):
        payload = {**self.VALID_PAYLOAD, 'last_period_start': 'bad-date'}
        response = self.client.post('/api/log-run/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_run_before_period_returns_400(self):
        payload = {
            **self.VALID_PAYLOAD,
            'date': '2024-05-01T08:00:00Z',
            'last_period_start': '2024-06-01T00:00:00Z',
        }
        response = self.client.post('/api/log-run/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_zero_pace_returns_400(self):
        payload = {**self.VALID_PAYLOAD, 'pace': 0}
        response = self.client.post('/api/log-run/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_zero_distance_returns_400(self):
        payload = {**self.VALID_PAYLOAD, 'distance': 0}
        response = self.client.post('/api/log-run/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_motivation_out_of_range_returns_400(self):
        payload = {**self.VALID_PAYLOAD, 'motivation_level': 11}
        response = self.client.post('/api/log-run/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_exertion_out_of_range_returns_400(self):
        payload = {**self.VALID_PAYLOAD, 'exertion_level': 0}
        response = self.client.post('/api/log-run/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_request_rejected(self):
        unauthenticated = APIClient()
        response = unauthenticated.post('/api/log-run/', self.VALID_PAYLOAD, format='json')
        self.assertIn(response.status_code, [
            status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN
        ])

    def test_phase_correctly_calculated_for_follicular(self):
        # Day 8 of cycle → Follicular
        payload = {**self.VALID_PAYLOAD, 'date': '2024-06-09T08:00:00Z'}
        response = self.client.post('/api/log-run/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['calculated_phase'], 'Follicular')


# ─────────────────────────────────────────────────────────────────────────────
#  /api/all-phases-comparison/
# ─────────────────────────────────────────────────────────────────────────────

class AllPhasesComparisonTest(BaseAPITestCase):

    def test_no_data_returns_404(self):
        response = self.client.get('/api/all-phases-comparison/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_with_run_data_returns_all_phases(self):
        from django.utils import timezone
        RunEntry.objects.create(
            user=self.user, date=timezone.now(),
            pace=5.0, distance=5.0, motivation_level=7, exertion_level=6,
            cycle_phase='Follicular', cycle_id=1,
        )
        response = self.client.get('/api/all-phases-comparison/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('phases', response.data)
        self.assertEqual(len(response.data['phases']), 4)

    def test_response_structure(self):
        from django.utils import timezone
        RunEntry.objects.create(
            user=self.user, date=timezone.now(),
            pace=5.5, distance=10.0, motivation_level=8, exertion_level=7,
            cycle_phase='Luteal', cycle_id=2,
        )
        response = self.client.get('/api/all-phases-comparison/')
        self.assertIn('current_cycle', response.data)
        self.assertIn('previous_cycle', response.data)

    def test_unauthenticated_rejected(self):
        response = APIClient().get('/api/all-phases-comparison/')
        self.assertIn(response.status_code, [401, 403])


# ─────────────────────────────────────────────────────────────────────────────
#  /api/user_tracking/
# ─────────────────────────────────────────────────────────────────────────────

class UserTrackingPreferencesTest(BaseAPITestCase):

    def test_returns_empty_lists_for_new_user(self):
        response = self.client.get('/api/user_tracking/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['trackables'], [])
        self.assertEqual(response.data['symptoms'], [])

    def test_returns_users_trackables(self):
        t = Trackable.objects.create(name='Sleep')
        UserTrackable.objects.create(user=self.user, trackable=t)
        response = self.client.get('/api/user_tracking/')
        self.assertIn('Sleep', response.data['trackables'])

    def test_returns_users_symptoms(self):
        s = Symptom.objects.create(name='Cramps')
        UserSymptom.objects.create(user=self.user, symptom=s)
        response = self.client.get('/api/user_tracking/')
        self.assertIn('Cramps', response.data['symptoms'])

    def test_unauthenticated_rejected(self):
        response = APIClient().get('/api/user_tracking/')
        self.assertIn(response.status_code, [401, 403])


# ─────────────────────────────────────────────────────────────────────────────
#  /api/advice/today/
# ─────────────────────────────────────────────────────────────────────────────

class TodayAdviceTest(BaseAPITestCase):

    def test_no_cycle_data_returns_empty_advice(self):
        response = self.client.get('/api/advice/today/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data['phase'])
        self.assertEqual(response.data['advice'], [])
        self.assertIn('message', response.data)

    def test_with_cycle_data_returns_phase(self):
        Cycle.objects.create(
            user=self.user,
            period_start_date=date.today() - timedelta(days=5),
        )
        response = self.client.get('/api/advice/today/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data['phase'])
        self.assertIn('cycle_day', response.data)

    def test_custom_date_param(self):
        Cycle.objects.create(
            user=self.user,
            period_start_date=date(2024, 6, 1),
        )
        response = self.client.get('/api/advice/today/?date=2024-06-08')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['date'], '2024-06-08')

    def test_invalid_date_param_returns_400(self):
        response = self.client.get('/api/advice/today/?date=not-a-date')
        self.assertEqual(response.status_code, 400)

    def test_unauthenticated_rejected(self):
        response = APIClient().get('/api/advice/today/')
        self.assertIn(response.status_code, [401, 403])


# ─────────────────────────────────────────────────────────────────────────────
#  /api/advice/phase/<phase>/
# ─────────────────────────────────────────────────────────────────────────────

class PhaseAdviceTest(BaseAPITestCase):

    def test_valid_phase_returns_advice_list(self):
        response = self.client.get('/api/advice/phase/menstrual/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('advice', response.data)
        self.assertIsInstance(response.data['advice'], list)

    def test_invalid_phase_returns_400(self):
        response = self.client.get('/api/advice/phase/badphase/')
        self.assertEqual(response.status_code, 400)

    def test_all_valid_phases_accepted(self):
        for phase in ('menstrual', 'follicular', 'ovulatory', 'luteal'):
            response = self.client.get(f'/api/advice/phase/{phase}/')
            self.assertEqual(response.status_code, 200, msg=f'Failed for phase: {phase}')

    def test_returns_only_generic_rules(self):
        AdviceRule.objects.create(
            phase='follicular', condition_type='none',
            advice_category='training', title='Generic tip',
            advice_text='Do some runs.', is_generic=True,
        )
        AdviceRule.objects.create(
            phase='follicular', condition_type='symptom',
            advice_category='recovery', title='Non-generic tip',
            advice_text='Rest up.', is_generic=False,
        )
        response = self.client.get('/api/advice/phase/follicular/')
        titles = [a['title'] for a in response.data['advice']]
        self.assertIn('Generic tip', titles)
        self.assertNotIn('Non-generic tip', titles)


# ─────────────────────────────────────────────────────────────────────────────
#  /api/race-goal/
# ─────────────────────────────────────────────────────────────────────────────

class RaceGoalViewTest(BaseAPITestCase):

    def test_get_no_goal_returns_has_race_goal_false(self):
        response = self.client.get('/api/race-goal/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['has_race_goal'])

    def test_get_with_active_goal(self):
        RaceGoal.objects.create(
            user=self.user, race_type='5k',
            race_date=date(2099, 1, 1), is_active=True
        )
        response = self.client.get('/api/race-goal/')
        self.assertTrue(response.data['has_race_goal'])
        self.assertEqual(response.data['race_type'], '5k')

    def test_post_missing_race_type_returns_400(self):
        response = self.client.post('/api/race-goal/', {
            'race_date': '2099-06-01'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_invalid_race_type_returns_400(self):
        response = self.client.post('/api/race-goal/', {
            'race_type': 'ultramarathon',
            'race_date': '2099-06-01'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_non_fun_without_race_date_returns_400(self):
        response = self.client.post('/api/race-goal/', {
            'race_type': '10k'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_past_race_date_returns_400(self):
        response = self.client.post('/api/race-goal/', {
            'race_type': '10k',
            'race_date': '2020-01-01',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_fun_mode_without_date_succeeds(self):
        Cycle.objects.create(
            user=self.user, period_start_date=date.today() - timedelta(days=5)
        )
        response = self.client.post('/api/race-goal/', {
            'race_type': 'fun',
            'race_name': '',
        }, format='json')
        self.assertIn(response.status_code, [
            status.HTTP_201_CREATED, status.HTTP_200_OK
        ])
        self.assertTrue(RaceGoal.objects.filter(user=self.user, race_type='fun').exists())

    def test_post_deactivates_previous_goal(self):
        RaceGoal.objects.create(
            user=self.user, race_type='5k',
            race_date=date(2099, 1, 1), is_active=True
        )
        Cycle.objects.create(
            user=self.user, period_start_date=date.today() - timedelta(days=5)
        )
        self.client.post('/api/race-goal/', {
            'race_type': 'fun',
            'race_name': '',
        }, format='json')
        active_goals = RaceGoal.objects.filter(user=self.user, is_active=True)
        self.assertEqual(active_goals.count(), 1)
        self.assertEqual(active_goals.first().race_type, 'fun')

    def test_post_invalid_goal_time_format_returns_400(self):
        response = self.client.post('/api/race-goal/', {
            'race_type': '5k',
            'race_date': '2099-06-01',
            'goal_time': 'not-a-time',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_rejected(self):
        response = APIClient().get('/api/race-goal/')
        self.assertIn(response.status_code, [401, 403])


# ─────────────────────────────────────────────────────────────────────────────
#  /api/prescribed-sessions/
# ─────────────────────────────────────────────────────────────────────────────

class PrescribedSessionListViewTest(BaseAPITestCase):

    def setUp(self):
        super().setUp()
        self.cycle = Cycle.objects.create(
            user=self.user, period_start_date=date.today() - timedelta(days=5)
        )

    def test_empty_returns_zero_count(self):
        response = self.client.get('/api/prescribed-sessions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_lists_sessions(self):
        PrescribedSession.objects.create(
            user=self.user, cycle=self.cycle,
            session_type='easy', cycle_phase='Follicular',
            prescribed_date=date.today() + timedelta(days=2),
            distance=5.0,
        )
        response = self.client.get('/api/prescribed-sessions/')
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['sessions'][0]['session_type'], 'easy')

    def test_status_filter_pending(self):
        PrescribedSession.objects.create(
            user=self.user, cycle=self.cycle, session_type='easy',
            cycle_phase='Follicular',
            prescribed_date=date.today() + timedelta(days=1), distance=5.0,
        )
        PrescribedSession.objects.create(
            user=self.user, cycle=self.cycle, session_type='tempo',
            cycle_phase='Ovulatory',
            prescribed_date=date.today() + timedelta(days=3), distance=8.0,
            status='completed',
        )
        response = self.client.get('/api/prescribed-sessions/?status=pending')
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['sessions'][0]['status'], 'pending')

    def test_invalid_status_filter_returns_400(self):
        response = self.client.get('/api/prescribed-sessions/?status=invalid')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_rejected(self):
        response = APIClient().get('/api/prescribed-sessions/')
        self.assertIn(response.status_code, [401, 403])
