from rest_framework.decorators import api_view, APIView, permission_classes
from rest_framework.response import Response
from datetime import datetime, timedelta, date
from django.utils.dateparse import parse_datetime
from django.db.models import Avg, Count
from .utils import calculate_cycle_phase, get_phase_recommendations
from .models import CyclePhaseEntry, UserProfile, RunEntry, TrackableLog, Symptom, ActivePhase, PrescribedSession, RaceGoal
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import AllowAny
from django.contrib.auth.models import User
from rest_framework import status, generics
from .serializers import RegisterSerializer, TrackableLogCreateSerializer, UserTrackable, UserSymptom, CycleSampleLogCreateSerializer, CycleSampleLog, SymptomLogSerializer, Cycle, SymptomLog, UserTrackingDashboardSerializer, CycleDayLogCreateSerializer, CycleSampleLogSerializer, SymptomLogWriteSerializer
from .adviceService import get_advice_for_user, get_user_cycle_context
from .services.phase_service import check_and_update_phase, force_phase_reset, get_active_phase

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
        'cycle_day': phase_info['cycle_day'],  # Day of menstrual cycle
        'days_until_next_phase': phase_info['days_until_next_phase'],
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
@permission_classes([IsAuthenticated])
def all_phases_comparison(request):
    """
    Get comparison for all phases at once.
    URL: /api/all-phases-comparison/
    """
    phases = ['Menstruation', 'Follicular', 'Ovulatory', 'Luteal']
    results = []
    
    # Get the overall latest cycle number
    
    user = request.user

    latest_cycle_entry = (
        RunEntry.objects
        .filter(user=user)
        .order_by('-cycle_id')
        .first()
    )
    
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
@permission_classes([IsAuthenticated])
def log_run(request):
# {
#     "date",
#     "pace",
#     "distance",
#     "motivation_level",
#     "last_period_start"
# }
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


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer

# TRACKABLE ITEMS ------------------------------------------------
# @permission_classes([IsAuthenticated])
class TrackableLogCreateView(generics.CreateAPIView):
    serializer_class = TrackableLogCreateSerializer
    queryset = TrackableLog.objects.all()

class UserTrackingPreferencesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        trackables = (
            UserTrackable.objects
            .filter(user=user)
            .select_related("trackable")
            .values_list("trackable__name", flat=True)
        )

        symptoms = (
            UserSymptom.objects
            .filter(user=user)
            .select_related("symptom")
            .values_list("symptom__name", flat=True)
        )

        return Response({
            "trackables": list(trackables),
            "symptoms": list(symptoms)
        })

#CYCLELOG ------------------------------------------------
@permission_classes([IsAuthenticated])
class CycleSampleLogCreateView(generics.CreateAPIView):
    serializer_class = CycleSampleLogCreateSerializer

    def get_queryset(self):
        return CycleSampleLog.objects.filter(user=self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

# SYMPTOMS ------------------------------------------------
@permission_classes([IsAuthenticated])
class SymptomLogCreateView(generics.CreateAPIView):
    serializer_class = SymptomLogWriteSerializer

    def get_queryset(self):
        return SymptomLog.objects.filter(user=self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

# GET USER DATA ------------------------------------------------
@permission_classes([IsAuthenticated])
class UserTrackingDashboardView(APIView):

    def get(self, request):
        user = request.user

        # Fetch all tracked data
        trackables = TrackableLog.objects.filter(user=user).select_related("trackable")
        symptoms = SymptomLog.objects.filter(user=user).select_related("symptom")
        cycles = Cycle.objects.filter(user=user).prefetch_related("samples__symptoms")

        # Serialize data
        serializer = UserTrackingDashboardSerializer({
            "trackables": trackables,
            "symptoms": symptoms,
            "cycles": cycles,
        })

        # Calculate current cycle info from the latest cycle
        latest_cycle = cycles.order_by("-period_start_date").first()
        cycle_info = {}
        if latest_cycle:
            try:
                last_period_dt = datetime.combine(latest_cycle.period_start_date, datetime.min.time())
                phase_info = calculate_cycle_phase(last_period_dt, datetime.now())
                cycle_info = {
                "calculated_phase": phase_info["phase"],
                "cycle_day": phase_info["cycle_day"],
                "days_until_next_phase": phase_info["days_until_next_phase"],
                "last_period_start": phase_info["last_period_start"],
                }
            except Exception as e:
                cycle_info = {"error": f"Cycle phase calculation failed: {str(e)}"}

            # Merge everything in response
        response_data = serializer.data
        response_data.update({"current_cycle": cycle_info})

        return Response(response_data)


# LOG CYCLE + SYMPTOMS ------------------------------------------------
@permission_classes([IsAuthenticated])
class LogCycleDayView(APIView):

    def post(self, request):
        serializer = CycleDayLogCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        data = serializer.validated_data

        cycle = Cycle.objects.get(id=data["cycle_id"], user=user)

        date_logged = data["date_logged"]

        # calculate day of cycle
        day_of_cycle = (date_logged - cycle.period_start_date).days + 1

        sample = CycleSampleLog.objects.create(
            user=user,
            cycle=cycle,
            date_logged=date_logged,
            day_of_cycle=day_of_cycle,
            flow_type=data["flow_type"],
            notes=data.get("notes", "")
        )

        symptom_names = data.get("symptoms", [])

        for name in symptom_names:
            symptom = Symptom.objects.get(name=name)

            sample.symptoms.add(symptom)

            SymptomLog.objects.update_or_create(
                user=user,
                symptom=symptom,
                date=date_logged,
                defaults={
                    "notes": data.get("notes", "")
                }
            )

        return Response(
            CycleSampleLogSerializer(sample).data,
            status=status.HTTP_201_CREATED
        )


# ADVICE ON TRACKABLES ------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def today_advice(request):
    target_date = datetime.today().date()  
    date_param  = request.query_params.get('date')
    if date_param:
        try:
            target_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)

    phase, cycle_day = get_user_cycle_context(request.user, target_date)

    if phase is None:
        return Response({
            'date':      str(target_date),
            'phase':     None,
            'cycle_day': None,
            'advice':    [],
            'message':   'Log your period to start receiving personalised advice.'
        })

    return Response({
        'date':      str(target_date),
        'phase':     phase,
        'cycle_day': cycle_day,
        'advice':    get_advice_for_user(request.user, target_date),
    })




@api_view(['GET'])
@permission_classes([IsAuthenticated])
def phase_advice(request, phase):
    from .models import AdviceRule

    valid = {'menstrual', 'follicular', 'ovulatory', 'luteal'}
    if phase not in valid:
        return Response({'error': f'Phase must be one of: {", ".join(valid)}'}, status=400)

    rules = AdviceRule.objects.filter(phase=phase, is_generic=True).order_by('advice_category', 'priority')
    return Response({
        'phase':  phase,
        'advice': [{'id': str(r.id), 'category': r.advice_category, 'title': r.title, 'body': r.advice_text} for r in rules]
    })

# CALENDAR ENDPOINT ------------------------------------------------------
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cycle_calendar(request):
    user = request.user
    cycles = Cycle.objects.filter(user=user).order_by('period_start_date')

    print(f"🐞 All cycles for {user.username}: {[(c.period_start_date, c.period_end_date) for c in cycles]}")
    print(f"🐞 Today: {date.today()}")

    if not cycles.exists():
        return Response([])

    # --- Compute averages ---
    cycle_list = list(cycles)

    # Average menstrual length from period_start to period_end
    menstrual_lengths = []
    for c in cycle_list:
        if c.period_end_date and c.period_start_date:
            length = (c.period_end_date - c.period_start_date).days + 1
            menstrual_lengths.append(max(length, 1))
    avg_menstrual = round(sum(menstrual_lengths) / len(menstrual_lengths)) if menstrual_lengths else 5

    # Average cycle length from gap between start dates
    cycle_lengths = []
    for i in range(len(cycle_list) - 1):
        gap = (cycle_list[i + 1].period_start_date - cycle_list[i].period_start_date).days
        cycle_lengths.append(gap)
    avg_cycle = round(sum(cycle_lengths) / len(cycle_lengths)) if cycle_lengths else 28

    # --- Generate days from most recent cycle ---
    # Take the most recent cycle whose start date is on or before today:
    today = date.today()
    past_cycles = [c for c in cycle_list if c.period_start_date <= today]
    last_logged = past_cycles[-1] if past_cycles else cycle_list[-1]

    # Roll forward from last logged start date using avg cycle length
    # until we find the predicted cycle that contains today
    predicted_start = last_logged.period_start_date
    while predicted_start + timedelta(days=avg_cycle) <= today:
        predicted_start += timedelta(days=avg_cycle)

    # Use predicted_start instead of current_cycle.period_start_date
    start_date = predicted_start

    # print(f"🐞 Selected current_cycle start: {current_cycle.period_start_date}")


    luteal_length = 14
    ovulation_length = 1
    follicular_length = max(avg_cycle - avg_menstrual - luteal_length - ovulation_length, 3)

    phases = (
        [('menstruation', avg_menstrual)] +
        [('follicular', follicular_length)] +
        [('ovulation', ovulation_length)] +
        [('luteal', luteal_length)]
    )

    days = []
    day_number = 1
    current_date = start_date

    for phase_name, length in phases:
        for _ in range(length):
            days.append({
                'day_of_cycle': day_number,
                'date': current_date.isoformat(),
                'phase': phase_name,
                'workout_type': None
            })
            day_number += 1
            current_date += timedelta(days=1)

    return Response(days)


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



# TRAINING BLOCK VIEWS -----------------------------------------------

class ActivePhaseView(APIView):
    permission_classes = [IsAuthenticated]
 
    def get(self, request):
        user = request.user
 
        active_phase, transitioned = check_and_update_phase(user)
 
        if not active_phase:
            return Response({
                'phase':     None,
                'message':   'No cycle data found. Log your period to get started.',
            }, status=status.HTTP_200_OK)
 
        return Response({
            'phase':                    active_phase.phase,
            'day_of_cycle':             active_phase.day_of_cycle,
            'phase_start_date':         str(active_phase.phase_start_date),
            'predicted_next_phase_date': str(active_phase.predicted_next_phase_date),
            'phase_transitioned_today': transitioned,
            'cycle_id':                 str(active_phase.cycle.id),
            'last_checked':             active_phase.last_checked.isoformat(),
        }, status=status.HTTP_200_OK)
 
 
# =============================================================
#  2. PrescribedSessionListView
#  GET /api/prescribed-sessions/
#  GET /api/prescribed-sessions/?status=pending
#  Returns prescribed sessions for the authenticated user.
#  Automatically marks expired pending sessions as skipped
#  before returning results.
# =============================================================
 
class PrescribedSessionListView(APIView):
    permission_classes = [IsAuthenticated]
 
    def get(self, request):
        user = request.user
        status_filter = request.query_params.get('status', None)
 
        # Auto-expire any pending sessions past their 3-day grace window
        pending_sessions = PrescribedSession.objects.filter(
            user=user,
            status='pending'
        )
        
        for session in pending_sessions:
            if session.prescribed_date and session.is_expired:
                session.status = 'skipped'
                session.save(update_fields=['status', 'updated_at'])
 
        # Build queryset
        queryset = PrescribedSession.objects.filter(user=user).select_related('cycle', 'completed_run')
 
        if status_filter:
            valid_statuses = ['pending', 'completed', 'skipped']
            if status_filter not in valid_statuses:
                return Response({
                    'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
                }, status=status.HTTP_400_BAD_REQUEST)
            queryset = queryset.filter(status=status_filter)
 
        sessions = []
        for s in queryset:
            sessions.append({
                'id':                str(s.id),
                'session_type':      s.session_type,
                'cycle_phase':       s.cycle_phase,
                'prescribed_date':   str(s.prescribed_date),
                'distance':          float(s.distance),
                'status':            s.status,
                'is_expired':        s.is_expired,
                'cycle_id':          str(s.cycle.id),
                'completed_run_id':  s.completed_run.id if s.completed_run else None,
            })
 
        return Response({
            'count':    len(sessions),
            'sessions': sessions,
        }, status=status.HTTP_200_OK)
 
 
# =============================================================
#  3. CompleteBaselineRunView
#  POST /api/prescribed-sessions/complete/
#  Marks a prescribed session as completed, creates a RunEntry
#  with is_baseline=True, and links them together.
#
#  Request body:
#  {
#    "prescribed_session_id": "uuid",
#    "pace": 5.45,
#    "distance": 5.0,
#    "motivation_level": 7,
#    "date": "2025-03-16T08:00:00Z"
#  }
# =============================================================
 
class CompleteBaselineRunView(APIView):
    permission_classes = [IsAuthenticated]
 
    def post(self, request):
        user = request.user
 
        # ── Validate required fields ──────────────────────────
        required = ['prescribed_session_id', 'pace', 'distance', 'motivation_level', 'date']
        missing  = [f for f in required if f not in request.data]
        if missing:
            return Response({
                'error':          'Missing required fields',
                'missing_fields': missing,
            }, status=status.HTTP_400_BAD_REQUEST)
 
        # ── Fetch the prescribed session ──────────────────────
        try:
            session = PrescribedSession.objects.get(
                id=request.data['prescribed_session_id'],
                user=user,
            )
        except PrescribedSession.DoesNotExist:
            return Response({
                'error': 'Prescribed session not found',
            }, status=status.HTTP_404_NOT_FOUND)
 
        if session.status == 'completed':
            return Response({
                'error': 'This session has already been completed',
            }, status=status.HTTP_400_BAD_REQUEST)
 
        # ── Validate numeric fields ───────────────────────────
        try:
            pace             = float(request.data['pace'])
            distance         = float(request.data['distance'])
            motivation_level = int(request.data['motivation_level'])
 
            if pace <= 0:
                raise ValueError('Pace must be greater than 0')
            if distance <= 0:
                raise ValueError('Distance must be greater than 0')
            if not (1 <= motivation_level <= 10):
                raise ValueError('Motivation level must be between 1 and 10')
 
        except (ValueError, TypeError) as e:
            return Response({
                'error':  'Invalid numeric values',
                'detail': str(e),
            }, status=status.HTTP_400_BAD_REQUEST)
 
        # ── Validate and parse date ───────────────────────────
        try:
            run_date = datetime.fromisoformat(
                request.data['date'].replace('Z', '+00:00')
            )
        except (ValueError, AttributeError):
            return Response({
                'error':  'Invalid date format',
                'detail': 'Expected ISO8601 format (e.g. 2025-03-16T08:00:00Z)',
            }, status=status.HTTP_400_BAD_REQUEST)
 
        # ── Get current phase for the run entry ───────────────
        active = get_active_phase(user)
        cycle_phase = active.phase if active else session.cycle_phase
 
        # ── Calculate cycle_id ────────────────────────────────
        first_entry = RunEntry.objects.filter(user=user).order_by('date').first()
        if first_entry:
            days_since_first = (run_date.date() - first_entry.date.date()).days
            cycle_id = (days_since_first // 28) + 1
        else:
            cycle_id = 1
 
        # ── Create the RunEntry ───────────────────────────────
        run_entry = RunEntry.objects.create(
            user=user,
            date=run_date,
            pace=pace,
            distance=distance,
            motivation_level=motivation_level,
            cycle_phase=cycle_phase,
            cycle_id=cycle_id,
            is_baseline=True,
            baseline_phase=session.cycle_phase,
        )
 
        # ── Mark session as completed and link the run ────────
        session.status        = 'completed'
        session.completed_run = run_entry
        session.save(update_fields=['status', 'completed_run', 'updated_at'])
 
        return Response({
            'success':              True,
            'run_entry_id':         run_entry.id,
            'prescribed_session_id': str(session.id),
            'cycle_phase':          cycle_phase,
            'is_baseline':          True,
            'baseline_phase':       session.cycle_phase,
        }, status=status.HTTP_201_CREATED)
 
 
# =============================================================
#  4. RaceGoalView
#  GET  /api/race-goal/  — returns the user's active race goal
#  POST /api/race-goal/  — creates a new race goal
#
#  POST request body:
#  {
#    "race_type": "10k",
#    "race_date": "2025-06-01",   (omit or null for fun mode)
#    "goal_time": "00:55:00"      (optional HH:MM:SS)
#  }
# =============================================================
 
class RaceGoalView(APIView):
    permission_classes = [IsAuthenticated]
 
    def get(self, request):
        user = request.user
 
        goal = RaceGoal.objects.filter(user=user, is_active=True).first()
 
        if not goal:
            return Response({
                'race_goal': None,
                'message':   'No active race goal. Set one to build a training plan.',
            }, status=status.HTTP_200_OK)
 
        return Response({
            'id':         str(goal.id),
            'race_type':  goal.race_type,
            'race_date':  str(goal.race_date) if goal.race_date else None,
            'goal_time':  str(goal.goal_time) if goal.goal_time else None,
            'is_active':  goal.is_active,
            'created_at': goal.created_at.isoformat(),
        }, status=status.HTTP_200_OK)
 
    def post(self, request):
        user = request.user
 
        # ── Validate race_type ────────────────────────────────
        race_type = request.data.get('race_type')
        valid_types = ['5k', '10k', 'half_marathon', 'marathon', 'fun']
        if not race_type or race_type not in valid_types:
            return Response({
                'error':  'Invalid or missing race_type',
                'detail': f'Must be one of: {", ".join(valid_types)}',
            }, status=status.HTTP_400_BAD_REQUEST)
 
        # ── Validate race_date ────────────────────────────────
        race_date = None
        if race_type != 'fun':
            raw_date = request.data.get('race_date')
            if not raw_date:
                return Response({
                    'error':  'race_date is required for non-fun race types',
                    'detail': 'Provide a date in YYYY-MM-DD format, or set race_type to "fun"',
                }, status=status.HTTP_400_BAD_REQUEST)
            try:
                race_date = date.fromisoformat(raw_date)
                if race_date <= date.today():
                    return Response({
                        'error':  'Invalid race_date',
                        'detail': 'Race date must be in the future',
                    }, status=status.HTTP_400_BAD_REQUEST)
            except ValueError:
                return Response({
                    'error':  'Invalid race_date format',
                    'detail': 'Expected YYYY-MM-DD',
                }, status=status.HTTP_400_BAD_REQUEST)
 
        # ── Validate goal_time (optional) ─────────────────────
        goal_time = None
        raw_time  = request.data.get('goal_time')
        if raw_time:
            try:
                from datetime import timedelta
                parts     = raw_time.split(':')
                goal_time = timedelta(
                    hours=int(parts[0]),
                    minutes=int(parts[1]),
                    seconds=int(parts[2]),
                )
            except (ValueError, IndexError):
                return Response({
                    'error':  'Invalid goal_time format',
                    'detail': 'Expected HH:MM:SS (e.g. 00:55:00)',
                }, status=status.HTTP_400_BAD_REQUEST)
 
        # ── Deactivate existing goals then create new one ──────
        RaceGoal.objects.filter(user=user, is_active=True).update(is_active=False)
 
        goal = RaceGoal.objects.create(
            user=user,
            race_type=race_type,
            race_date=race_date,
            goal_time=goal_time,
            is_active=True,
        )
 
        return Response({
            'success':   True,
            'id':        str(goal.id),
            'race_type': goal.race_type,
            'race_date': str(goal.race_date) if goal.race_date else None,
            'goal_time': str(goal.goal_time) if goal.goal_time else None,
            'is_active': goal.is_active,
        }, status=status.HTTP_201_CREATED)