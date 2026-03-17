from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import TrackableLog, SymptomLog
from .adviceService import invalidate_advice_cache


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


@receiver(post_delete, sender=SymptomLog)
def invalidate_advice_on_symptom_delete(sender, instance, **kwargs):
    print(f"[Signal] SymptomLog DELETED for user={instance.user.id} on date={instance.date}")
    invalidate_advice_cache(instance.user, instance.date)
    print(f"[Signal] Advice cache invalidated for user={instance.user.id} on {instance.date}")