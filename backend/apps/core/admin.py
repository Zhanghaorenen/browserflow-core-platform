from django.contrib import admin
from .models import (
    Task,
    TaskRun,
    TaskStep,
    TaskResult,
    TaskTemplate,
    Approval,
    Preferences,
)

for model in [Task, TaskRun, TaskStep, TaskResult, TaskTemplate, Approval, Preferences]:
    admin.site.register(model)
