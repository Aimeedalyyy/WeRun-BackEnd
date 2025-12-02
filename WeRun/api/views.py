from rest_framework.decorators import api_view
from rest_framework.response import Response
import datetime


@api_view(['GET'])
def test_endpoint(request):
    x = datetime.datetime.now()
    """Simple test endpoint to verify API connectivity."""
    test_object = {
        'test_name': 'API Connection Test',
        'test_number': 1,
        'current_date': x
    }
    return Response(test_object)


@api_view(['GET'])
def analysis_endpoint(request):
    """ Endpoint for the analysis page"""
    analysis_objects = [
    {
        "phase_name": "Menstrual",
        "avg_pace": 6.12,
        "motivation_level": 4,
        "stat_per_avg": "Lower energy is normal — go easier on yourself.",
        "stat_per_mood": "Mood may dip; prioritise rest and recovery."
    },
    {
        "phase_name": "Follicular",
        "avg_pace": 5.48,
        "motivation_level": 7,
        "stat_per_avg": "Energy is rising — great time for building momentum.",
        "stat_per_mood": "Mood often improves and creativity increases."
    },
    {
        "phase_name": "Ovulatory",
        "avg_pace": 5.32,
        "motivation_level": 8,
        "stat_per_avg": "Peak performance window — pacing feels easier.",
        "stat_per_mood": "Confidence and social energy are typically higher."
    },
    {
        "phase_name": "Luteal",
        "avg_pace": 5.66,
        "motivation_level": 9,
        "stat_per_avg": "You are so back",
        "stat_per_mood": "You are so back still"
    }
    ]
    return Response(analysis_objects)
