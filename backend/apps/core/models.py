import uuid
from django.conf import settings
from django.db import models


class Status(models.TextChoices):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Task(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=160)
    description = models.TextField()
    target_url = models.URLField(blank=True, max_length=2000)
    allowed_domains = models.JSONField(default=list)
    model_name = models.CharField(max_length=100, default="mock")
    max_steps = models.PositiveIntegerField(default=20)
    timeout_seconds = models.PositiveIntegerField(default=120)
    output_type = models.CharField(max_length=10, default="json")
    output_schema = models.JSONField(default=dict, blank=True)
    parameters = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=24, choices=Status, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "status", "created_at"])]


class TaskRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="runs")
    attempt_number = models.PositiveIntegerField()
    celery_task_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=24, choices=Status, default=Status.PENDING)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration = models.FloatField(default=0)
    step_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    error_type = models.CharField(max_length=100, blank=True)
    engine = models.CharField(max_length=30, default="mock")
    usage = models.JSONField(default=dict)

    class Meta:
        ordering = ["-attempt_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["task", "attempt_number"], name="unique_task_attempt"
            )
        ]


class TaskStep(models.Model):
    task_run = models.ForeignKey(
        TaskRun, on_delete=models.CASCADE, related_name="steps"
    )
    step_number = models.PositiveIntegerField()
    action_name = models.CharField(max_length=100)
    action_parameters = models.JSONField(default=dict)
    page_url = models.TextField(blank=True)
    status = models.CharField(max_length=24, default="SUCCEEDED")
    duration = models.FloatField(default=0)
    error_message = models.TextField(blank=True)
    screenshot_path = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["step_number", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["task_run", "step_number"], name="unique_run_step"
            )
        ]


class TaskResult(models.Model):
    task_run = models.OneToOneField(
        TaskRun, on_delete=models.CASCADE, related_name="result"
    )
    raw_result = models.TextField()
    structured_result = models.JSONField()
    validation_status = models.CharField(max_length=24)
    source_urls = models.JSONField(default=list)
    file_path = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Approval(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    task_run = models.ForeignKey(
        TaskRun, on_delete=models.CASCADE, related_name="approvals"
    )
    operation_type = models.CharField(max_length=60)
    operation_summary = models.JSONField()
    payload = models.JSONField()
    fingerprint = models.CharField(max_length=64)
    status = models.CharField(max_length=20, default="PENDING")
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class TaskTemplate(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True
    )
    name = models.CharField(max_length=160)
    description = models.TextField()
    prompt_template = models.TextField()
    default_config = models.JSONField(default=dict)
    output_schema = models.JSONField(default=dict)
    requires_approval = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class Preferences(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    model_name = models.CharField(max_length=100, default="mock")
    max_steps = models.PositiveIntegerField(default=20)
    timeout_seconds = models.PositiveIntegerField(default=120)
    allowed_domains = models.JSONField(default=list)
    theme = models.CharField(max_length=10, default="light")
