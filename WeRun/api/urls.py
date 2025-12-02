# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('api/test/', views.test_endpoint, name='test-endpoint'),
     path('api/analysis/', views.analysis_endpoint, name='analysis-endpoint'),
    #api/test/
]

