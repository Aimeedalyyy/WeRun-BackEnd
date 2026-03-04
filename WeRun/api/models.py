from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import AbstractUser
from django.conf import settings
import uuid


class User(AbstractUser):
    affiliated_user = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='affiliates'
    )
    
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

class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    average_cycle_length = models.IntegerField(default=28)
    last_period_sync = models.DateTimeField(null=True, blank=True)
    last_period_start = models.DateTimeField(null=True, blank=True)
    last_period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

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

    severity = models.PositiveSmallIntegerField()  # 1–5 scale
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "symptom", "date")
        indexes = [
            models.Index(fields=["user", "date"]),
        ]

    def __str__(self):
        return f"{self.user} {self.symptom} {self.date}"
