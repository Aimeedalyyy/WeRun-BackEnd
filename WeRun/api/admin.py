from django.contrib import admin
from .models import CyclePhaseEntry, RunEntry

admin.site.register(CyclePhaseEntry)
admin.site.register(RunEntry)