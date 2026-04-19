"""
Tests for authentication edge cases and cross-user authorisation.

Two distinct concerns are tested here:

  1. Authentication — does the API correctly accept/reject credentials?
       - Valid Token auth
       - Invalid / missing token
       - JWT access token (valid, expired, malformed)

  2. Authorisation — even with valid credentials, can user A access
     user B's data?  These tests catch missing ownership checks in views
     (e.g. a missing `user=request.user` filter).

Views covered additionally here:
  - CompletePrescribedRunView (the most security-sensitive write endpoint)
  - UserTrackingDashboardView
  - LogCycleDayView
  - PrescribedSessionListView (cross-user isolation)
"""

from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model

from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from api.models import (
    Cycle,
    PrescribedSession,
    RaceGoal,
    RunEntry,
    Symptom,
    SymptomLog,
    Trackable,
    TrackableLog,
    UserTrackable,
)

User = get_user_model()

# All endpoints that require authentication.
AUTHENTICATED_ENDPOINTS = [
    ('GET',  '/api/user_tracking/'),
    ('GET',  '/api/all-phases-comparison/'),
    ('GET',  '/api/advice/today/'),
    ('GET',  '/api/prescribed-sessions/'),
    ('GET',  '/api/race-goal/'),
    ('GET',  '/api/active-phase/'),
    ('GET',  '/api/user-info/'),
    ('POST', '/api/log-run/'),
    ('POST', '/api/prescribed-sessions/complete/'),
    ('POST', '/api/race-goal/'),
]


def _make_user(username, password='testpass'):
    return User.objects.create_user(username=username, password=password)


def _token_client(user):
    """Returns an APIClient authenticated via DRF Token."""
    client = APIClient()
    token, _ = Token.objects.get_or_create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    return client


def _jwt_client(user):
    """Returns an APIClient authenticated via JWT Bearer token."""
    client = APIClient()
    access = AccessToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(access)}')
    return client


# ─────────────────────────────────────────────────────────────────────────────
#  Authentication — Token auth
# ─────────────────────────────────────────────────────────────────────────────

class TestTokenAuthentication(TestCase):

    def setUp(self):
        self.user = _make_user('tokenuser')
        self.client = _token_client(self.user)

    def test_valid_token_grants_access(self):
        response = self.client.get('/api/user_tracking/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_missing_token_returns_401_or_403(self):
        response = APIClient().get('/api/user_tracking/')
        self.assertIn(response.status_code, [
            status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN
        ])

    def test_invalid_token_returns_401(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Token not_a_real_token')
        response = client.get('/api/user_tracking/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_malformed_auth_header_returns_401(self):
        # Header present but not in 'Token <key>' format.
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Bearer this_is_a_token_not_jwt')
        response = client.get('/api/user_tracking/')
        # JWT auth will reject a malformed bearer too — either 401 is fine.
        self.assertIn(response.status_code, [
            status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN
        ])

    def test_all_protected_endpoints_reject_unauthenticated_requests(self):
        """
        Smoke test: every endpoint that requires auth must return 401/403
        when called with no credentials.
        """
        anon = APIClient()
        for method, url in AUTHENTICATED_ENDPOINTS:
            with self.subTest(method=method, url=url):
                call = getattr(anon, method.lower())
                response = call(url, format='json')
                self.assertIn(
                    response.status_code,
                    [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
                    msg=f"{method} {url} should require auth"
                )


# ─────────────────────────────────────────────────────────────────────────────
#  Authentication — JWT auth
# ─────────────────────────────────────────────────────────────────────────────

class TestJWTAuthentication(TestCase):

    def setUp(self):
        self.user = _make_user('jwtuser')

    def test_valid_jwt_grants_access(self):
        client = _jwt_client(self.user)
        response = client.get('/api/user_tracking/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_expired_jwt_returns_401(self):
        # Manually create a token with a negative lifetime so it is
        # already expired by the time we use it.
        access = AccessToken.for_user(self.user)
        access.set_exp(lifetime=-timedelta(seconds=1))

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(access)}')
        response = client.get('/api/user_tracking/')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_random_string_as_jwt_returns_401(self):
        # A fuzz-style check: a random string in the Bearer header must
        # never produce a 200 or crash.
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Bearer xyzINVALIDjwt.token.here')
        response = client.get('/api/user_tracking/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_jwt_obtain_pair_endpoint_returns_tokens(self):
        response = APIClient().post('/auth/token/', {
            'username': 'jwtuser',
            'password': 'testpass',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_jwt_refresh_returns_new_access_token(self):
        # Obtain a refresh token, then exchange it for a new access token.
        tokens = APIClient().post('/auth/token/', {
            'username': 'jwtuser',
            'password': 'testpass',
        }, format='json').data

        response = APIClient().post('/auth/token/refresh/', {
            'refresh': tokens['refresh']
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_wrong_password_returns_401(self):
        response = APIClient().post('/auth/token/', {
            'username': 'jwtuser',
            'password': 'wrongpassword',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_nonexistent_user_returns_401(self):
        response = APIClient().post('/auth/token/', {
            'username': 'ghost_user_xyz',
            'password': 'doesntmatter',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ─────────────────────────────────────────────────────────────────────────────
#  Authorisation — cross-user data isolation
#  User A must never be able to read or write User B's data, even with a
#  valid token. These tests catch missing `user=request.user` ownership filters.
# ─────────────────────────────────────────────────────────────────────────────

class TestCrossUserIsolation(TestCase):

    def setUp(self):
        self.user_a = _make_user('user_a')
        self.user_b = _make_user('user_b')
        self.client_a = _token_client(self.user_a)

        # Give user B a cycle and a prescribed session.
        self.cycle_b = Cycle.objects.create(
            user=self.user_b,
            period_start_date=date.today() - timedelta(days=7),
        )
        self.session_b = PrescribedSession.objects.create(
            user=self.user_b,
            cycle=self.cycle_b,
            session_type='easy',
            cycle_phase='Follicular',
            prescribed_date=date.today() + timedelta(days=1),
            distance=5.0,
            status='pending',
        )

    def test_prescribed_sessions_only_returns_own_sessions(self):
        # User A makes their own session, then lists sessions —
        # user B's session must not appear.
        cycle_a = Cycle.objects.create(
            user=self.user_a,
            period_start_date=date.today() - timedelta(days=7),
        )
        PrescribedSession.objects.create(
            user=self.user_a, cycle=cycle_a,
            session_type='easy', cycle_phase='Follicular',
            prescribed_date=date.today() + timedelta(days=2), distance=5.0,
        )

        response = self.client_a.get('/api/prescribed-sessions/')
        session_ids = [s['id'] for s in response.data['sessions']]

        self.assertNotIn(str(self.session_b.id), session_ids)

    def test_completing_another_users_session_returns_404(self):
        # User A attempts to mark User B's session as completed.
        # The view fetches with `user=request.user` so it must not find it.
        from django.utils import timezone

        payload = {
            'prescribed_session_id': str(self.session_b.id),
            'pace': 5.5,
            'distance': 5.0,
            'motivation_level': 7,
            'exertion_level': 6,
            'date': timezone.now().isoformat(),
        }
        response = self.client_a.post(
            '/api/prescribed-sessions/complete/', payload, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_tracking_only_returns_own_data(self):
        # Give user B a trackable — user A's response must not include it.
        t = Trackable.objects.create(name='UserBSleep')
        UserTrackable.objects.create(user=self.user_b, trackable=t)

        response = self.client_a.get('/api/user_tracking/')
        self.assertNotIn('UserBSleep', response.data.get('trackables', []))

    def test_race_goal_only_returns_own_goal(self):
        # User B creates an active race goal — user A's GET should return
        # has_race_goal=False (since user A has none of their own).
        RaceGoal.objects.create(
            user=self.user_b, race_type='5k',
            race_date=date.today() + timedelta(days=100),
            race_name='', is_active=True,
        )
        response = self.client_a.get('/api/race-goal/')
        self.assertFalse(response.data['has_race_goal'])

    def test_log_run_is_attributed_to_authenticated_user_not_payload(self):
        # Verify the run is saved against request.user, not any user ID
        # that could theoretically be injected into the request body.
        payload = {
            'date': '2024-06-10T08:00:00Z',
            'pace': 5.5,
            'distance': 5.0,
            'motivation_level': 7,
            'exertion_level': 6,
            'last_period_start': '2024-06-01T00:00:00Z',
        }
        self.client_a.post('/api/log-run/', payload, format='json')

        self.assertEqual(RunEntry.objects.filter(user=self.user_a).count(), 1)
        self.assertEqual(RunEntry.objects.filter(user=self.user_b).count(), 0)


# ─────────────────────────────────────────────────────────────────────────────
#  Views with lower existing coverage — tested here alongside auth
# ─────────────────────────────────────────────────────────────────────────────

class TestUserTrackingDashboardView(TestCase):
    """GET /api/user-info/"""

    def setUp(self):
        self.user = _make_user('dashuser')
        self.client = _token_client(self.user)

    def test_returns_200_for_authenticated_user(self):
        response = self.client.get('/api/user-info/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_response_has_trackables_symptoms_cycles_keys(self):
        response = self.client.get('/api/user-info/')
        for key in ('trackables', 'symptoms', 'cycles'):
            self.assertIn(key, response.data)

    def test_trackable_logs_appear_in_response(self):
        t = Trackable.objects.create(name='DashSleep')
        TrackableLog.objects.create(
            user=self.user, trackable=t,
            date=date.today(), value_numeric=8.0
        )
        response = self.client.get('/api/user-info/')
        names = [item['name'] for item in response.data['trackables']]
        self.assertIn('DashSleep', names)

    def test_current_cycle_info_present_when_cycle_exists(self):
        Cycle.objects.create(
            user=self.user,
            period_start_date=date.today() - timedelta(days=5),
        )
        response = self.client.get('/api/user-info/')
        self.assertIn('current_cycle', response.data)
        self.assertIn('calculated_phase', response.data['current_cycle'])

    def test_unauthenticated_returns_401_or_403(self):
        response = APIClient().get('/api/user-info/')
        self.assertIn(response.status_code, [401, 403])


class TestLogCycleDayView(TestCase):
    """POST /api/cycle-log/"""

    def setUp(self):
        self.user = _make_user('cyclelog')
        self.client = _token_client(self.user)
        self.cycle = Cycle.objects.create(
            user=self.user, period_start_date=date.today() - timedelta(days=5)
        )

    def test_valid_post_creates_cycle_sample(self):
        from api.models import CycleSampleLog
        payload = {
            'cycle_id': str(self.cycle.id),
            'date_logged': str(date.today()),
            'flow_type': 2,
        }
        response = self.client.post('/api/cycle-log/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(CycleSampleLog.objects.filter(user=self.user).exists())

    def test_auto_calculates_day_of_cycle(self):
        from api.models import CycleSampleLog
        payload = {
            'cycle_id': str(self.cycle.id),
            'date_logged': str(date.today()),
            'flow_type': 1,
        }
        self.client.post('/api/cycle-log/', payload, format='json')
        sample = CycleSampleLog.objects.filter(user=self.user).first()
        # 5 days ago means today = day 6.
        self.assertEqual(sample.day_of_cycle, 6)

    def test_invalid_cycle_id_raises_error(self):
        payload = {
            'cycle_id': '00000000-0000-0000-0000-000000000000',
            'date_logged': str(date.today()),
            'flow_type': 1,
        }
        # NOTE: LogCycleDayView calls Cycle.objects.get() without a try/except,
        # so a non-existent cycle_id currently causes an unhandled DoesNotExist
        # exception and returns HTTP 500.  This test documents that known gap —
        # the view should be updated to return 404 instead.
        # raise_request_exception=False prevents the test client from re-raising
        # the exception so we can inspect the actual HTTP response.
        self.client.raise_request_exception = False
        response = self.client.post('/api/cycle-log/', payload, format='json')
        self.client.raise_request_exception = True  # restore default

        # Accepted outcomes: 404 (ideal) or 500 (current, documented bug).
        # Neither should silently return 201 and create phantom data.
        self.assertNotEqual(response.status_code, status.HTTP_201_CREATED)

    def test_with_known_symptoms_creates_symptom_logs(self):
        symptom = Symptom.objects.create(name='Cramps')
        payload = {
            'cycle_id': str(self.cycle.id),
            'date_logged': str(date.today()),
            'flow_type': 2,
            'symptoms': ['Cramps'],
        }
        self.client.post('/api/cycle-log/', payload, format='json')
        self.assertTrue(
            SymptomLog.objects.filter(user=self.user, symptom=symptom).exists()
        )

    def test_unauthenticated_returns_401_or_403(self):
        response = APIClient().post('/api/cycle-log/', {}, format='json')
        self.assertIn(response.status_code, [401, 403])


class TestCompletePrescribedRunView(TestCase):
    """POST /api/prescribed-sessions/complete/"""

    def setUp(self):
        self.user = _make_user('completeuser')
        self.client = _token_client(self.user)
        self.cycle = Cycle.objects.create(
            user=self.user, period_start_date=date.today() - timedelta(days=7)
        )
        self.session = PrescribedSession.objects.create(
            user=self.user, cycle=self.cycle,
            session_type='easy', cycle_phase='Follicular',
            prescribed_date=date.today(), distance=5.0, status='pending',
        )

    def _valid_payload(self, session=None):
        s = session or self.session
        return {
            'prescribed_session_id': str(s.id),
            'pace': 5.5,
            'distance': 5.0,
            'motivation_level': 7,
            'exertion_level': 6,
            'date': f'{date.today()}T08:00:00Z',
        }

    def test_valid_completion_returns_201(self):
        response = self.client.post(
            '/api/prescribed-sessions/complete/', self._valid_payload(), format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_session_status_becomes_completed(self):
        self.client.post(
            '/api/prescribed-sessions/complete/', self._valid_payload(), format='json'
        )
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'completed')

    def test_run_entry_is_created(self):
        self.client.post(
            '/api/prescribed-sessions/complete/', self._valid_payload(), format='json'
        )
        self.assertEqual(RunEntry.objects.filter(user=self.user).count(), 1)

    def test_completing_already_completed_session_returns_400(self):
        self.session.status = 'completed'
        self.session.save()
        response = self.client.post(
            '/api/prescribed-sessions/complete/', self._valid_payload(), format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_completing_rest_session_returns_400(self):
        rest = PrescribedSession.objects.create(
            user=self.user, cycle=self.cycle,
            session_type='rest', cycle_phase='Follicular',
            prescribed_date=date.today() + timedelta(days=1), distance=0.0,
        )
        response = self.client.post(
            '/api/prescribed-sessions/complete/', self._valid_payload(rest), format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_required_field_returns_400(self):
        payload = self._valid_payload()
        del payload['pace']
        response = self.client.post(
            '/api/prescribed-sessions/complete/', payload, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('pace', response.data['missing_fields'])

    def test_invalid_pace_returns_400(self):
        payload = {**self._valid_payload(), 'pace': -1}
        response = self.client.post(
            '/api/prescribed-sessions/complete/', payload, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_motivation_out_of_range_returns_400(self):
        payload = {**self._valid_payload(), 'motivation_level': 0}
        response = self.client.post(
            '/api/prescribed-sessions/complete/', payload, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_baseline_5k_session_is_flagged_is_baseline_true(self):
        baseline = PrescribedSession.objects.create(
            user=self.user, cycle=self.cycle,
            session_type='baseline_5k', cycle_phase='Follicular',
            prescribed_date=date.today() + timedelta(days=2), distance=5.0,
        )
        payload = self._valid_payload(baseline)
        response = self.client.post(
            '/api/prescribed-sessions/complete/', payload, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['is_baseline'])
