from django.contrib import admin
from .models import (
    User,
    UserProfile,
    CyclePhaseEntry,
    RunEntry,
    Trackable,
    UserTrackable,
    TrackableLog,
    Symptom,
    UserSymptom,
    SymptomLog
)


from django.contrib import admin
from .models import CyclePhaseEntry, RunEntry
from django.contrib.auth import get_user_model

User = get_user_model()


# -------------------------
# Custom User Admin
# -------------------------
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    # Show all fields of the custom user model
    list_display = [field.name for field in User._meta.fields]


# -------------------------
# CyclePhaseEntry Admin
# -------------------------
@admin.register(CyclePhaseEntry)
class CyclePhaseEntryAdmin(admin.ModelAdmin):
    list_display = [field.name for field in CyclePhaseEntry._meta.fields]


# -------------------------
# RunEntry Admin
# -------------------------
@admin.register(RunEntry)
class RunEntryAdmin(admin.ModelAdmin):
    list_display = [field.name for field in RunEntry._meta.fields]
    


# -------------------------
# Trackable Admin
# -------------------------
@admin.register(Trackable)
class TrackableAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Trackable._meta.fields]


# -------------------------
# UserTrackable Admin
# -------------------------
@admin.register(UserTrackable)
class UserTrackableAdmin(admin.ModelAdmin):
    list_display = [field.name for field in UserTrackable._meta.fields]


# -------------------------
# TrackableLog Admin
# -------------------------
@admin.register(TrackableLog)
class TrackableLogAdmin(admin.ModelAdmin):
    list_display = [field.name for field in TrackableLog._meta.fields]


# -------------------------
# Symptom Admin
# -------------------------
@admin.register(Symptom)
class SymptomAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Symptom._meta.fields]


# -------------------------
# UserSymptom Admin
# -------------------------
@admin.register(UserSymptom)
class UserSymptomAdmin(admin.ModelAdmin):
    list_display = [field.name for field in UserSymptom._meta.fields]


# -------------------------
# SymptomLog Admin
# -------------------------
@admin.register(SymptomLog)
class SymptomLogAdmin(admin.ModelAdmin):
    list_display = [field.name for field in SymptomLog._meta.fields]