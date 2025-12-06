from rest_framework.decorators import api_view
from rest_framework.response import Response
from datetime import datetime
from django.utils.dateparse import parse_datetime
from django.db.models import Avg, Count
from .utils import calculate_cycle_phase, get_phase_recommendations
from .models import CyclePhaseEntry, UserProfile, RunEntry
from rest_framework.permissions import IsAuthenticated
from django.utils.dateparse import parse_datetime
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from django.contrib.auth.models import User
from rest_framework import status



#Sample
@api_view(['POST'])
def test_endpoint(request):
    todays_date = datetime.now()
    
    last_period = request.data.get('last_period_start')
    
    if not last_period:
        return Response({
            'error': 'Missing required field',
            'detail': 'last_period_start is required',
            'field': 'last_period_start'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    period_date = parse_datetime(last_period)

    if period_date is None:
        return Response({
            'error': 'Invalid last_period_start format',
            'detail': 'Expected ISO8601 format (e.g., 2025-11-20T00:00:00Z)',
            'field': 'last_period_start'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    try:
        phase_info = calculate_cycle_phase(period_date, todays_date)
    except Exception as e:
        return Response({
            'error': 'Phase calculation failed',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    test_object = {
        'test_name': 'API Connection Test',
        'test_number': 1,
        'current_date': todays_date,
        'calculated_phase': phase_info['phase'],
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


@api_view(['GET'])
def phase_comparison(request, phase_name):
    """
    Compare current cycle phase stats with previous cycle.
    URL: /api/phase-comparison/<phase_name>/
    
    Returns:
    - phase: The phase name
    - current_avg_pace: Average pace for latest cycle
    - current_avg_motivation: Average motivation for latest cycle
    - pace_change_percent: Percentage change from previous cycle (negative = improvement)
    - motivation_change_percent: Percentage change from previous cycle
    """
    
    # Validate phase name
    valid_phases = ['Menstrual', 'Follicular', 'Ovulatory', 'Luteal']
    if phase_name not in valid_phases:
        return Response({
            'error': f'Invalid phase. Must be one of: {", ".join(valid_phases)}'
        }, status=400)
    
    # Get the latest cycle number
    latest_cycle = CyclePhaseEntry.objects.filter(
        phase_name=phase_name
    ).values('cycle_id').distinct().order_by('-cycle_id').first()
    
    if not latest_cycle:
        return Response({
            'error': 'No data found for this phase'
        }, status=404)
    
    current_cycle_id = latest_cycle['cycle_id']
    previous_cycle_id = current_cycle_id - 1
    
    # Get current cycle stats
    current_stats = CyclePhaseEntry.objects.filter(
        cycle_id=current_cycle_id,
        phase_name=phase_name
    ).aggregate(
        avg_pace=Avg('pace'),
        avg_motivation=Avg('motivation_level')
    )
    
    # Get previous cycle stats
    previous_stats = CyclePhaseEntry.objects.filter(
        cycle_id=previous_cycle_id,
        phase_name=phase_name
    ).aggregate(
        avg_pace=Avg('pace'),
        avg_motivation=Avg('motivation_level')
    )
    
    # Calculate percentage changes
    pace_change = None
    motivation_change = None
    
    if previous_stats['avg_pace'] and current_stats['avg_pace']:
        # Note: Lower pace is better (faster running), so we invert the calculation
        pace_change = ((float(current_stats['avg_pace']) - float(previous_stats['avg_pace'])) 
                      / float(previous_stats['avg_pace'])) * 100
    
    if previous_stats['avg_motivation'] and current_stats['avg_motivation']:
        motivation_change = ((float(current_stats['avg_motivation']) - float(previous_stats['avg_motivation'])) 
                            / float(previous_stats['avg_motivation'])) * 100
    
    return Response({
        'phase': phase_name,
        'current_cycle': current_cycle_id,
        'previous_cycle': previous_cycle_id,
        'current_avg_pace': round(float(current_stats['avg_pace']), 2) if current_stats['avg_pace'] else None,
        'current_avg_motivation': round(float(current_stats['avg_motivation']), 2) if current_stats['avg_motivation'] else None,
        'pace_change_percent': round(pace_change, 2) if pace_change is not None else None,
        'motivation_change_percent': round(motivation_change, 2) if motivation_change is not None else None,
        'pace_improved': pace_change < 0 if pace_change is not None else None  # True if pace got faster
    })



@api_view(['GET'])
def all_phases_comparison(request):
    """
    Get comparison for all phases at once.
    URL: /api/all-phases-comparison/
    """
    phases = ['Menstrual', 'Follicular', 'Ovulatory', 'Luteal']
    results = []
    
    # Get the overall latest cycle number
    latest_cycle_entry = RunEntry.objects.order_by('-cycle_id').first()
    
    if not latest_cycle_entry:
        return Response({
            'error': 'No run data found',
            'current_cycle': None,
            'previous_cycle': None,
            'phases': []
        }, status=status.HTTP_404_NOT_FOUND)
    
    current_cycle_id = latest_cycle_entry.cycle_id
    previous_cycle_id = current_cycle_id - 1
    
    for phase in phases:
        # Get current cycle stats for this phase
        current_stats = RunEntry.objects.filter(
            cycle_id=current_cycle_id,
            cycle_phase=phase
        ).aggregate(
            avg_pace=Avg('pace'),
            avg_motivation=Avg('motivation_level'),
            run_count=Count('id')
        )
        
        # Get previous cycle stats for this phase
        previous_stats = RunEntry.objects.filter(
            cycle_id=previous_cycle_id,
            cycle_phase=phase
        ).aggregate(
            avg_pace=Avg('pace'),
            avg_motivation=Avg('motivation_level'),
            run_count=Count('id')
        )
        
        # Calculate percentage changes
        pace_change = None
        motivation_change = None
        
        if previous_stats['avg_pace'] and current_stats['avg_pace']:
            pace_change = ((float(current_stats['avg_pace']) - float(previous_stats['avg_pace'])) 
                          / float(previous_stats['avg_pace'])) * 100
        
        if previous_stats['avg_motivation'] and current_stats['avg_motivation']:
            motivation_change = ((float(current_stats['avg_motivation']) - float(previous_stats['avg_motivation'])) 
                                / float(previous_stats['avg_motivation'])) * 100
        
        # Always include all phases
        results.append({
            'phase': phase,
            'current_avg_pace': round(float(current_stats['avg_pace']), 2) if current_stats['avg_pace'] else None,
            'previous_avg_pace': round(float(previous_stats['avg_pace']), 2) if previous_stats['avg_pace'] else None,
            'current_avg_motivation': round(float(current_stats['avg_motivation']), 2) if current_stats['avg_motivation'] else None,
            'previous_avg_motivation': round(float(previous_stats['avg_motivation']), 2) if previous_stats['avg_motivation'] else None,
            'current_run_count': current_stats['run_count'],
            'previous_run_count': previous_stats['run_count'],
            'pace_change_percent': round(pace_change, 2) if pace_change is not None else None,
            'motivation_change_percent': round(motivation_change, 2) if motivation_change is not None else None,
            'pace_improved': pace_change < 0 if pace_change is not None else None,
            'has_comparison_data': previous_stats['run_count'] > 0
        })
    
    return Response({
        'current_cycle': current_cycle_id,
        'previous_cycle': previous_cycle_id,
        'phases': results
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
# @permission_classes([IsAuthenticated])
def log_run(request):
    """
    Mobile sends: date, pace, distance, motivation, last_period_start
    Backend calculates and stores: phase, cycle_id
    """
    # Validate required fields
    required_fields = ['date', 'pace', 'distance', 'motivation_level', 'last_period_start']
    missing_fields = [field for field in required_fields if field not in request.data]
    
    if missing_fields:
        return Response({
            'error': 'Missing required fields',
            'missing_fields': missing_fields
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Validate and parse dates
    try:
        run_date = datetime.fromisoformat(request.data['date'].replace('Z', '+00:00'))
    except (ValueError, AttributeError, TypeError) as e:
        return Response({
            'error': 'Invalid date format',
            'detail': 'Expected ISO8601 format (e.g., 2025-12-03T08:30:00Z)',
            'field': 'date'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    last_period = request.data.get('last_period_start')
    period_date = parse_datetime(last_period)
    
    if period_date is None:
        return Response({
            'error': 'Invalid last_period_start format',
            'detail': 'Expected ISO8601 format (e.g., 2025-11-20T00:00:00Z)',
            'field': 'last_period_start'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Validate numeric fields
    try:
        pace = float(request.data['pace'])
        distance = float(request.data['distance'])
        motivation_level = int(request.data['motivation_level'])
        
        if pace <= 0:
            return Response({
                'error': 'Invalid pace value',
                'detail': 'Pace must be greater than 0'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if distance <= 0:
            return Response({
                'error': 'Invalid distance value',
                'detail': 'Distance must be greater than 0'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not (1 <= motivation_level <= 10):
            return Response({
                'error': 'Invalid motivation_level',
                'detail': 'Motivation level must be between 1 and 10'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except (ValueError, TypeError) as e:
        return Response({
            'error': 'Invalid numeric values',
            'detail': 'pace and distance must be numbers, motivation_level must be an integer'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Validate date logic
    if run_date < period_date:
        return Response({
            'error': 'Invalid date relationship',
            'detail': 'Run date cannot be before last period start date'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Calculate phase automatically
    try:
        phase_info = calculate_cycle_phase(period_date, run_date)
    except Exception as e:
        return Response({
            'error': 'Phase calculation failed',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Calculate cycle ID (number of cycles since tracking started)
    try:
        first_entry = RunEntry.objects.filter(user=request.user).order_by('date').first()
        if first_entry:
            days_since_first = (run_date.date() - first_entry.date.date()).days
            cycle_id = (days_since_first // 28) + 1
        else:
            cycle_id = 1
    except Exception as e:
        return Response({
            'error': 'Cycle ID calculation failed',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Create run entry
    try:
        run_entry = RunEntry.objects.create(
            user=request.user,
            date=run_date,
            pace=pace,
            distance=distance,
            motivation_level=motivation_level,
            cycle_phase=phase_info['phase'],
            cycle_id=cycle_id
        )
    except Exception as e:
        return Response({
            'error': 'Failed to create run entry',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response({
        'success': True,
        'entry_id': run_entry.id,
        'calculated_phase': phase_info['phase'],
        'cycle_id': cycle_id,
        'cycle_day': phase_info['cycle_day']
    }, status=status.HTTP_201_CREATED)





# NOT Tested
@api_view(['GET'])
# @permission_classes([IsAuthenticated])
@permission_classes([AllowAny]) 
def get_user_insights(request):
    """
    Get comprehensive insights across multiple cycles
    """

    # if not request.user.is_authenticated:
    #     user = User.objects.get(id=1)  # Your superuser
    # else:
    #     user = request.user
    
    # Get last 3 cycles
    cycles = RunEntry.objects.filter(
        user= 1,
    ).values('cycle_id').distinct().order_by('-cycle_id')[:3]
    
    if not cycles:
        return Response({'message': 'No data available yet'}, status=200)
    
    cycle_ids = [c['cycle_id'] for c in cycles]
    
    # Get phase breakdown for each cycle
    insights = []
    for cycle_id in cycle_ids:
        cycle_stats = RunEntry.objects.filter(
            user= 1, 
            cycle_id=cycle_id
        ).values('cycle_phase').annotate(
            avg_pace=Avg('pace'),
            avg_motivation=Avg('motivation_level'),
            entry_count=Count('id')
        )
        
        insights.append({
            'cycle': cycle_id,
            'phases': list(cycle_stats)
        })
    
    # Find best performance phase
    all_phases = RunEntry.objects.filter(
        user= 1,
        cycle_id__in=cycle_ids
    ).values('cycle_phase').annotate(
        avg_pace=Avg('pace')
    ).order_by('avg_pace')
    
    best_phase = all_phases.first() if all_phases else None
    
    return Response({
        'insights': insights,
        'best_performance_phase': best_phase['cycle_phase'] if best_phase else None,
        'total_runs_logged': RunEntry.objects.filter(user=request.user).count()
  })

# NOT TESTED
@api_view(['POST'])
def sync_period_data(request):

    last_period_start = request.data.get('last_period_start')
    if not last_period_start:
        return Response({'error': 'last_period_start required'}, status=400)

    period_date = parse_datetime(last_period_start)
    if period_date is None:
        return Response({'error': 'Invalid ISO8601 date.'}, status=400)

    profile, created = UserProfile.objects.get_or_create(user=request.user)
    profile.last_period_sync = timezone.now()
    profile.save()

    phase_info = calculate_cycle_phase(period_date)

    historical_stats = CyclePhaseEntry.objects.filter(
        user=request.user,
        phase_name=phase_info['phase']
    ).aggregate(
        avg_pace=Avg('pace'),
        avg_motivation=Avg('motivation_level'),
        total_entries=Count('id')
    )

    recommendations = get_phase_recommendations(phase_info['phase'])

    return Response({
        'current_phase': phase_info,
        'historical_stats': historical_stats,
        'recommendations': recommendations
    })
