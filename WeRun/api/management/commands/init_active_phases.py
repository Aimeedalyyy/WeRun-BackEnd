# =============================================================
#  api/management/commands/init_active_phases.py
#
#  Usage:
#    docker exec -it werun_backend python manage.py init_active_phases
#
#  Options:
#    --username sarah_collins   run for a single user only
#    --force                    re-initialise even if record already exists
# =============================================================
 
from django.core.management.base import BaseCommand
from api.models import User
from api.services.phase_service import (
    initialise_active_phase,
    _fire_transition_events,
    _get_latest_cycle,
)
 
 
class Command(BaseCommand):
    help = 'Initialises ActivePhase records for all users who have cycle data'
 
    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Only initialise for this specific username',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Re-initialise even if an ActivePhase record already exists',
        )
 
    def handle(self, *args, **options):
        from api.models import ActivePhase
 
        username = options.get('username')
        force    = options.get('force')
 
        # ── Narrow to a single user if --username was passed ──
        if username:
            try:
                users = User.objects.filter(username=username)
                if not users.exists():
                    self.stderr.write(self.style.ERROR(f'User "{username}" not found'))
                    return
            except Exception as e:
                self.stderr.write(self.style.ERROR(str(e)))
                return
        else:
            users = User.objects.filter(cycles__isnull=False).distinct()
 
        if not users.exists():
            self.stdout.write(self.style.WARNING('No users with cycle data found'))
            return
 
        success = 0
        skipped = 0
        failed  = 0
 
        for user in users:
            try:
                from api.models import PrescribedSession
                already_exists = ActivePhase.objects.filter(user=user).exists()
 
                if already_exists and not force:
                    # ActivePhase exists — check if a PrescribedSession
                    # was ever created for the current phase. If not,
                    # fire the transition events now to create it.
                    active = ActivePhase.objects.get(user=user)
                    cycle  = _get_latest_cycle(user)
 
                    has_pending_session = PrescribedSession.objects.filter(
                        user=user,
                        cycle=cycle,
                        cycle_phase=active.phase,
                        session_type='baseline_5k',
                    ).exists()
 
                    if not has_pending_session:
                        _fire_transition_events(user, None, active.phase, cycle)
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'  ✓  {user.username}: ActivePhase already existed — '
                                f'prescribed session created for {active.phase}'
                            )
                        )
                        success += 1
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f'  ⟳  {user.username}: already fully initialised — skipping '
                                f'(use --force to overwrite)'
                            )
                        )
                        skipped += 1
                    continue
 
                # Fresh initialisation
                active = initialise_active_phase(user)
 
                if active:
                    # Fire transition events to create the PrescribedSession
                    cycle = _get_latest_cycle(user)
                    _fire_transition_events(user, None, active.phase, cycle)
 
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✓  {user.username}: '
                            f'{active.phase} — '
                            f'day {active.day_of_cycle} — '
                            f'next phase {active.predicted_next_phase_date} — '
                            f'baseline run prescribed'
                        )
                    )
                    success += 1
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  ✗  {user.username}: no cycle data found, skipped'
                        )
                    )
                    skipped += 1
 
            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f'  ✗  {user.username}: failed — {str(e)}')
                )
                failed += 1
