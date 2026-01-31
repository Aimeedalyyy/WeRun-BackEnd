# urls.py
from django.urls import path
from . import views
from .views import RegisterView

urlpatterns = [
    path('api/test/', views.test_endpoint, name='test-endpoint'),
    path('api/analysis/', views.analysis_endpoint, name='analysis-endpoint'),
    path('api/phase-comparison/<str:phase_name>/', views.phase_comparison, name='phase-comparison'),
    path('api/all-phases-comparison/', views.all_phases_comparison, name='all-phases-comparison'),
    path('api/sync-period/', views.sync_period_data, name='sync-period'),
    path('api/log-run/', views.log_run, name='log-run'),
    path('api/user-insights/', views.get_user_insights, name='user-insights'),

    path('api/register/', RegisterView.as_view()),

]
