# urls.py
from django.urls import path
from . import views
from .views import RegisterView, TrackableLogCreateView, UserTrackingPreferencesView, SymptomLogCreateView, CycleSampleLogCreateView, UserTrackingDashboardView, LogCycleDayView, cycle_calendar,ActivePhaseView, PrescribedSessionListView, CompletePrescribedRunView, RaceGoalView

urlpatterns = [
    path('api/test/', views.test_endpoint, name='test-endpoint'),

    # ANALYSIS ----------------------------------------------------------------------------------------
    path('api/phase-comparison/<str:phase_name>/', views.phase_comparison, name='phase-comparison'),
    path('api/all-phases-comparison/', views.all_phases_comparison, name='all-phases-comparison'),
    path('api/user-insights/', views.get_user_insights, name='user-insights'),
    # -------------------------------------------------------------------------------------------------

    # LOGGING -----------------------------------------------------------------------------------------
    path("api/symptoms/", SymptomLogCreateView.as_view(), name="log-symptom"),
    path("api/cycle-log/", LogCycleDayView.as_view(), name="log-cycle-day"),
    path("api/cycles/", CycleSampleLogCreateView.as_view(), name="log-cycle-sample"),
    path('api/log_trackables/', TrackableLogCreateView.as_view(), name='trackable-log-create'),
    path("api/user_tracking/", UserTrackingPreferencesView.as_view(), name="user-preferences"),
    path('api/sync-period/', views.sync_period_data, name='sync-period'),
    path('api/log-run/', views.log_run, name='log-run'),
    path('api/prescribed-sessions/', PrescribedSessionListView.as_view(), name='prescribed-sessions'),
    path('api/prescribed-sessions/complete/', CompletePrescribedRunView.as_view(), name='complete-baseline'),
    path('api/race-goal/', RaceGoalView.as_view(), name='race-goal'),
    path('api/active-phase/', ActivePhaseView.as_view(), name='active-phase'),
    # -------------------------------------------------------------------------------------------------
   
    # ADVICE ------------------------------------------------------------------------------------------
    path('api/advice/today/',views.today_advice,name='advice-today'),
    path('api/advice/phase/<str:phase>/', views.phase_advice, name='advice-phase'),
    # -------------------------------------------------------------------------------------------------
   
    # LOG IN ------------------------------------------------------------------------------------------
    path('api/register/', RegisterView.as_view()),
    # -------------------------------------------------------------------------------------------------

    # CALENDAR ----------------------------------------------------------------------------------------
    path("api/user-info/", UserTrackingDashboardView.as_view(), name="user-dashboard"),
    path('api/cycle-calendar/', cycle_calendar),
    # -------------------------------------------------------------------------------------------------
]
