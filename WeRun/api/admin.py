from django.contrib import admin
from .models import CyclePhaseEntry, RunEntry, User

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