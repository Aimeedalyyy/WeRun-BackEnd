from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import TrackableLog, SymptomLog
from .adviceService import invalidate_advice_cache
from .services.training_schedule_service import adjust_todays_session_for_symptoms
from django.utils import timezone


# ──────────────────────────────────────────────
# TrackableLog signals
# ──────────────────────────────────────────────

@receiver(post_save, sender=TrackableLog)
def invalidate_advice_on_trackable_save(sender, instance, created, **kwargs):
    action = "CREATED" if created else "UPDATED"
    print(f"[Signal] TrackableLog {action} for user={instance.user.id} on date={instance.date}")
    invalidate_advice_cache(instance.user, instance.date)
    print(f"[Signal] Advice cache invalidated for user={instance.user.id} on {instance.date}")


@receiver(post_delete, sender=TrackableLog)
def invalidate_advice_on_trackable_delete(sender, instance, **kwargs):
    print(f"[Signal] TrackableLog DELETED for user={instance.user.id} on date={instance.date}")
    invalidate_advice_cache(instance.user, instance.date)
    print(f"[Signal] Advice cache invalidated for user={instance.user.id} on {instance.date}")


# ──────────────────────────────────────────────
# SymptomLog signals
# ──────────────────────────────────────────────

@receiver(post_save, sender=SymptomLog)
def invalidate_advice_on_symptom_save(sender, instance, created, **kwargs):
    action = "CREATED" if created else "UPDATED"
    print(f"[Signal] SymptomLog {action} for user={instance.user.id} on date={instance.date}")
    invalidate_advice_cache(instance.user, instance.date)
    print(f"[Signal] Advice cache invalidated for user={instance.user.id} on {instance.date}")
    
    # Trigger session adjustment only if the symptom was logged for today
    if instance.date == timezone.localdate():
        print(f"[Signal] Symptom is for today -> adjusting today's session for user={instance.user.id}")
        try:
            adjust_todays_session_for_symptoms(instance.user)
            print(f"[Signal] Session adjustment complete for user={instance.user.id}")
        except Exception as e:
            # Don't let a downstream failure break the save; log and move on
            print(f"[Signal] Session adjustment FAILED for user={instance.user.id}: {e}")
    else:
        print(f"[Signal] Symptom is for {instance.date}, not today -> skipping session adjustment")


@receiver(post_delete, sender=SymptomLog)
def invalidate_advice_on_symptom_delete(sender, instance, **kwargs):
    print(f"[Signal] SymptomLog DELETED for user={instance.user.id} on date={instance.date}")
    invalidate_advice_cache(instance.user, instance.date)
    print(f"[Signal] Advice cache invalidated for user={instance.user.id} on {instance.date}")