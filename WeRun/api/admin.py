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
    SymptomLog,
    Cycle,
    CycleSampleLog,
    AdviceRule,
    DailyAdviceCache,
    ActivePhase,
    PrescribedSession,
    RaceGoal
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
    list_display        = [field.name for field in TrackableLog._meta.fields]
    list_filter         = ('trackable', 'date')
    search_fields       = ('user__username', 'trackable__name')
    date_hierarchy      = 'date'
    ordering            = ('-date',)
    list_select_related = ('user', 'trackable')


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


# -------------------------
# Cycle Admin
# -------------------------
@admin.register(Cycle)
class CycleAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Cycle._meta.fields]


# -------------------------
# CycleSampleLog Admin
# -------------------------
@admin.register(CycleSampleLog)
class CycleSampleLogAdmin(admin.ModelAdmin):
    list_display = [field.name for field in CycleSampleLog._meta.fields]

    
# -------------------------
# Advice Admin
# -------------------------


@admin.register(AdviceRule)
class AdviceRuleAdmin(admin.ModelAdmin):
    list_display  = ('title', 'phase', 'advice_category', 'condition_type', 'condition_key', 'priority', 'is_generic')
    list_filter   = ('phase', 'advice_category', 'condition_type', 'is_generic')
    search_fields = ('title', 'condition_key', 'advice_text')
    ordering      = ('phase', 'priority')


@admin.register(DailyAdviceCache)
class DailyAdviceCacheAdmin(admin.ModelAdmin):
    list_display  = ('user', 'date', 'updated_at')
    list_filter   = ('date',)
    search_fields = ('user__username',)
    ordering      = ('-date',)

# -------------------------
# ActivePhase Admin
# -------------------------
@admin.register(ActivePhase)
class ActivePhaseAdmin(admin.ModelAdmin):
    list_display        = ('user', 'phase', 'day_of_cycle', 'phase_start_date', 'predicted_next_phase_date', 'last_checked')
    list_filter         = ('phase',)
    search_fields       = ('user__username',)
    ordering            = ('user',)
    list_select_related = ('user', 'cycle')
 
 
# -------------------------
# PrescribedSession Admin
# -------------------------
@admin.register(PrescribedSession)
class PrescribedSessionAdmin(admin.ModelAdmin):
    list_display        = ('user', 'session_type', 'cycle_phase', 'prescribed_date', 'status', 'is_expired')
    list_filter         = ('session_type', 'cycle_phase', 'status')
    search_fields       = ('user__username',)
    ordering            = ('-prescribed_date',)
    list_select_related = ('user', 'cycle', 'completed_run')
    readonly_fields     = ('is_expired',)
 
 
# -------------------------
# RaceGoal Admin
# -------------------------
@admin.register(RaceGoal)
class RaceGoalAdmin(admin.ModelAdmin):
    list_display        = ('user', 'race_type', 'race_date', 'goal_time', 'is_active', 'created_at')
    list_filter         = ('race_type', 'is_active')
    search_fields       = ('user__username',)
    ordering            = ('-created_at',)
    list_select_related = ('user',)