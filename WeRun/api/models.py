from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import AbstractUser
from django.conf import settings
import uuid
from datetime import date, timedelta


class User(AbstractUser):
    affiliated_user = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='affiliates'
    )
    
class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    average_cycle_length = models.IntegerField(default=28)
    last_period_sync = models.DateTimeField(null=True, blank=True)
    last_period_start = models.DateTimeField(null=True, blank=True)
    last_period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"


# RUN ENTRIES  ------------------------------------------------
class RunEntry(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="run_entries"
    )

    date = models.DateTimeField()
    pace = models.DecimalField(max_digits=5, decimal_places=2)
    distance = models.DecimalField(max_digits=6, decimal_places=2)
    motivation_level = models.IntegerField()

    cycle_phase = models.CharField(max_length=50)  # Auto-calculated backend
    cycle_id = models.IntegerField()  # Auto-assigned backend

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']
        # indexes = [
        #     models.Index(fields=['user', 'cycle_id'], name="idx_user_cycle"),
        #     models.Index(fields=['user', 'cycle_phase'], name="idx_user_phase"),
        # ]

    def __str__(self):
        return f"{self.user.username} – {self.cycle_phase} – {self.date.date()}"


# TRACKABLE ITEMS ------------------------------------------------

class Trackable(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, unique=True)
    unit = models.CharField(max_length=50, blank=True)  # ml, hours, bpm, score
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    

class UserTrackable(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="trackables")
    trackable = models.ForeignKey(Trackable, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "trackable")

    def __str__(self):
        return f"{self.user} → {self.trackable}"

class TrackableLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="trackable_logs"
    )

    trackable = models.ForeignKey(
        Trackable,
        on_delete=models.CASCADE,
        related_name="logs"
    )

    date = models.DateField()

    value_numeric = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True
    )

    value_text = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "trackable", "date")
        indexes = [
            models.Index(fields=["user", "date"]),
        ]

    def __str__(self):
        return f"{self.user} {self.trackable} {self.date}"


# SYMPTOMS  ------------------------------------------------
class Symptom(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, unique=True)

    def __str__(self):
        return self.name

class UserSymptom(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="symptoms")
    symptom = models.ForeignKey(Symptom, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("user", "symptom")

    def __str__(self):
        return f"{self.user} → {self.symptom}"
    
class SymptomLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="symptom_logs"
    )

    symptom = models.ForeignKey(
        Symptom,
        on_delete=models.CASCADE,
        related_name="logs"
    )

    date = models.DateField()

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "symptom", "date")
        indexes = [
            models.Index(fields=["user", "date"]),
        ]

    def __str__(self):
        return f"{self.user} {self.symptom} {self.date}"


# PERIOD SAMPLES  ------------------------------------------------
class Cycle(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="cycles"
    )

    period_start_date = models.DateField()
    period_end_date = models.DateField(blank=True, null=True)

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} cycle starting {self.period_start_date}"

class CycleSampleLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="cycle_samples"
    )

    cycle = models.ForeignKey(
        Cycle,
        on_delete=models.CASCADE,
        related_name="samples"
    )

    date_logged = models.DateField()
    day_of_cycle = models.IntegerField()

    flow_type = models.IntegerField()
    notes = models.TextField(blank=True)

    symptoms = models.ManyToManyField(
        Symptom,
        blank=True,
        related_name="cycle_samples"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "cycle", "date_logged")
        indexes = [
            models.Index(fields=["user", "date_logged"]),
        ]

    def __str__(self):
        return f"{self.user} - {self.date_logged}"



 # DOESNT GET USED  ------------------------------------------------ 
class CyclePhaseEntry(models.Model):
    """
    Running & motivation data for a specific menstrual cycle phase,
    associated with a user.
    """

    PHASE_CHOICES = [
        ('Menstrual', 'Menstrual'),
        ('Follicular', 'Follicular'),
        ('Ovulatory', 'Ovulatory'),
        ('Luteal', 'Luteal'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cycle_phase_entries"
    )

    cycle_id = models.IntegerField(
        help_text="Cycle number identifier"
    )

    phase_name = models.CharField(
        max_length=50,
        choices=PHASE_CHOICES,
        help_text="Current menstrual cycle phase"
    )

    pace = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Running pace in minutes per kilometer"
    )

    motivation_level = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Motivation level from 1 to 10"
    )

    # entry_timestamp = models.DateTimeField(
    #     help_text="When this entry was recorded"
    # )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'cycle_phase_entries'
        # ordering = ['-entry_timestamp']
        indexes = [
            models.Index(fields=['user', 'cycle_id', 'phase_name'], name='idx_user_cycle_phase'),
            # models.Index(fields=['user', 'phase_name', 'entry_timestamp'], name='idx_user_phase_timestamp'),
        ]
        verbose_name = 'Cycle Phase Entry'
        verbose_name_plural = 'Cycle Phase Entries'

    def __str__(self):
        return f"{self.user.username} – Cycle {self.cycle_id} – {self.phase_name}"
    

# ADVICE ON TRACKABLES --------------------------------------------

class AdviceRule(models.Model):

    PHASE_CHOICES = [
        ('menstrual',  'Menstrual'),
        ('follicular', 'Follicular'),
        ('ovulatory',  'Ovulatory'),
        ('luteal',     'Luteal'),
        ('any',        'Any Phase'),
    ]

    CONDITION_TYPE_CHOICES = [
        ('none',               'No Condition (Phase Only)'),
        ('symptom',            'Symptom Logged Today'),
        ('trackable_numeric',  'Trackable — Numeric Threshold'),
        ('trackable_baseline', 'Trackable — vs Personal Baseline'),
    ]

    OPERATOR_CHOICES = [
        ('gte',              '>='),
        ('lte',              '<='),
        ('eq',               '=='),
        ('above_baseline',   'Above Personal Baseline'),
        ('below_baseline',   'Below Personal Baseline'),
    ]

    CATEGORY_CHOICES = [
        ('training',  'Training'),
        ('recovery',  'Recovery'),
        ('nutrition', 'Nutrition'),
        ('mindset',   'Mindset'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ── When to show ──────────────────────────────────────────────────────────
    phase         = models.CharField(max_length=20, choices=PHASE_CHOICES)
    cycle_day_min = models.IntegerField(null=True, blank=True)
    cycle_day_max = models.IntegerField(null=True, blank=True)

    # ── What data triggers it ─────────────────────────────────────────────────
    condition_type     = models.CharField(max_length=30, choices=CONDITION_TYPE_CHOICES, default='none')
    # For symptom rules  → exact symptom name e.g. "cramps"
    # For trackable rules → exact Trackable.name e.g. "Sleep", "Energy Level"
    condition_key      = models.CharField(max_length=120, blank=True)
    condition_operator = models.CharField(max_length=20, choices=OPERATOR_CHOICES, blank=True)
    condition_value    = models.FloatField(null=True, blank=True)

    # ── The advice itself ─────────────────────────────────────────────────────
    advice_category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    title           = models.CharField(max_length=100)
    advice_text     = models.TextField()
    priority        = models.IntegerField(default=5)   # lower number = higher priority
    is_generic      = models.BooleanField(default=False)  # fallback when no data logged

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['priority']

    def __str__(self):
        return f"[{self.phase}] {self.title}"


class DailyAdviceCache(models.Model):
    """
    Stores today's computed advice per user so the engine doesn't
    re-run on every app open. Cleared/overwritten each new day.
    """
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='advice_cache')
    date       = models.DateField()
    advice     = models.JSONField()   # serialised list of advice cards
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'date')

    def __str__(self):
        return f"{self.user} — advice {self.date}"
    
# PHASE FOR TRAINING BLOCKS --------------------------------------------

class ActivePhase(models.Model):
 
    PHASE_CHOICES = [
        ('Menstrual',  'Menstrual'),
        ('Follicular', 'Follicular'),
        ('Ovulatory',  'Ovulatory'),
        ('Luteal',     'Luteal'),
    ]
 
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='active_phase'
    )
    cycle = models.ForeignKey(
        Cycle,
        on_delete=models.CASCADE,
        related_name='active_phases'
    )
    phase = models.CharField(max_length=20, choices=PHASE_CHOICES)
    day_of_cycle = models.IntegerField()
    phase_start_date = models.DateField()
    predicted_next_phase_date = models.DateField()
    last_checked = models.DateTimeField(auto_now=True)
 
    def __str__(self):
        return f"{self.user} — {self.phase} since {self.phase_start_date}"
    
class PrescribedSession(models.Model):
 
    STATUS_CHOICES = [
        ('pending',   'Pending'),
        ('completed', 'Completed'),
        ('skipped',   'Skipped'),
    ]
 
    SESSION_TYPES = [
        ('baseline_5k', 'Baseline 5K'),
        ('easy',        'Easy Run'),
        ('moderate',    'Moderate Run'),
        ('tempo',       'Tempo Run'),
        ('long_run',    'Long Run'),
        ('rest',        'Rest Day'),
    ]
 
    PHASE_CHOICES = [
        ('Menstruation', 'Menstruation'),
        ('Follicular',   'Follicular'),
        ('Ovulatory',    'Ovulatory'),
        ('Luteal',       'Luteal'),
    ]
 
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
 
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='prescribed_sessions'
    )
    cycle = models.ForeignKey(
        Cycle,
        on_delete=models.CASCADE,
        related_name='prescribed_sessions'
    )
    race_goal = models.ForeignKey(
        'RaceGoal',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='prescribed_sessions'
    )  # null when in fun/tracking mode
 
    session_type = models.CharField(max_length=20, choices=SESSION_TYPES)
    cycle_phase  = models.CharField(max_length=20, choices=PHASE_CHOICES)
    prescribed_date = models.DateField()
    distance = models.DecimalField(max_digits=5, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
 
    # Linked once the user completes the run
    completed_run = models.OneToOneField(
        RunEntry,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='prescribed_session'
    )
 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        ordering = ['-prescribed_date']
        indexes = [
            models.Index(fields=['user', 'status'], name='idx_prescribed_user_status'),
            models.Index(fields=['user', 'cycle_phase'], name='idx_prescribed_user_phase'),
        ]
 
    def __str__(self):
        return f"{self.user.username} — {self.session_type} — {self.cycle_phase} — {self.status}"
 
    @property
    def is_expired(self):
        """
        A pending baseline run is valid for 3 days after prescription.
        After that it should be marked skipped.
        """        

        if self.status == 'pending' and self.prescribed_date:
            return date.today() > self.prescribed_date + timedelta(days=3)
        return False

class RaceGoal(models.Model):
 
    RACE_TYPES = [
        ('5k',            '5K'),
        ('10k',           '10K'),
        ('half_marathon', 'Half Marathon'),
        ('marathon',      'Marathon'),
        ('fun',           'Run for Fun'),
    ]
 
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
 
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='race_goals'
    )
 
    race_type  = models.CharField(max_length=20, choices=RACE_TYPES)
    race_date  = models.DateField(null=True, blank=True)   # null for fun mode
    goal_time  = models.DurationField(null=True, blank=True)  # optional target time
    is_active  = models.BooleanField(default=True)
 
    created_at = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        ordering = ['-created_at']
 
    def __str__(self):
        return f"{self.user.username} — {self.race_type} — {self.race_date or 'fun mode'}"
 