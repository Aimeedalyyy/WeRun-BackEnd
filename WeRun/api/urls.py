# urls.py
from django.urls import path
from . import views
from .views import RegisterView, TrackableLogCreateView, UserTrackingPreferencesView, SymptomLogCreateView, CycleSampleLogCreateView, UserTrackingDashboardView, LogCycleDayView, cycle_calendar,ActivePhaseView, PrescribedSessionListView, CompleteBaselineRunView, RaceGoalView

urlpatterns = [
    path('api/test/', views.test_endpoint, name='test-endpoint'),
    path('api/analysis/', views.analysis_endpoint, name='analysis-endpoint'),
    path('api/phase-comparison/<str:phase_name>/', views.phase_comparison, name='phase-comparison'),
    path('api/all-phases-comparison/', views.all_phases_comparison, name='all-phases-comparison'),
    path('api/sync-period/', views.sync_period_data, name='sync-period'),
    path('api/log-run/', views.log_run, name='log-run'),
    path('api/user-insights/', views.get_user_insights, name='user-insights'),

    path('api/register/', RegisterView.as_view()),

    #Endpoint for a user to log each trackable with values
    path('api/log_trackables/', TrackableLogCreateView.as_view(), name='trackable-log-create'),
    path("api/user_tracking/", UserTrackingPreferencesView.as_view(), name="user-preferences"),

    #Endpoint for a user to log each symptoms with values
    path("api/symptoms/", SymptomLogCreateView.as_view(), name="log-symptom"),
    # {
    # "symptom_name":"Abdominal Cramps",
    # "date": "2023-04-10"
    # }

    #Endpoint for a user to log each cycle
    path("api/cycles/", CycleSampleLogCreateView.as_view(), name="log-cycle-sample"),
    # {
    # "cycle_id": "e017f0fa-cc03-42c1-92a7-a90b42d34f69",
    # "date_logged": "2025-01-02",
    # "day_of_cycle": 1,
    # "flow_type": 1
    # }

    path("api/user-info/", UserTrackingDashboardView.as_view(), name="user-dashboard"),
    path("api/cycle-log/", LogCycleDayView.as_view(), name="log-cycle-day"),

    #Endpoints for Advice on Trackables 
    path('api/advice/today/',views.today_advice,name='advice-today'),
    path('api/advice/phase/<str:phase>/', views.phase_advice, name='advice-phase'),
    
    path('api/cycle-calendar/', cycle_calendar),

    # TRAINING BLOCK END POINTS 
    path('api/active-phase/', ActivePhaseView.as_view(), name='active-phase'),
    path('api/prescribed-sessions/', PrescribedSessionListView.as_view(), name='prescribed-sessions'),

    # Baseline run completed
    path('api/prescribed-sessions/complete/', CompleteBaselineRunView.as_view(), name='complete-baseline'),

    # Race Goals
    # GET  — returns the user's active race goal
    # POST — creates a new race goal (sets all others to is_active=False)
    # {
    #   "race_type": "10k",           (5k / 10k / half_marathon / marathon / fun)
    #   "race_date": "2025-06-01",    (omit for fun mode)
    #   "goal_time": "00:55:00"       (optional HH:MM:SS)
    # }
    path('api/race-goal/', RaceGoalView.as_view(), name='race-goal'),



]
