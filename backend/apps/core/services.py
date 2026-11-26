import json
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import Task, TaskRun, TaskStep, Approval, Status
from .security import redact, fingerprint

ACTIVE = {Status.PENDING, Status.RUNNING, Status.WAITING_APPROVAL}
TRANSITIONS = {
    Status.PENDING: {Status.RUNNING, Status.CANCELLED, Status.FAILED},
    Status.RUNNING: {
        Status.WAITING_APPROVAL,
        Status.SUCCEEDED,
        Status.FAILED,
        Status.CANCELLED,
    },
    Status.WAITING_APPROVAL: {Status.PENDING, Status.CANCELLED, Status.FAILED},
}


def emit(task_id, event="updated"):
    try:
        async_to_sync(get_channel_layer().group_send)(
            f"task.{task_id}",
            {"type": "task.event", "event": event, "task_id": str(task_id)},
        )
    except Exception:
        import logging

        logging.getLogger(__name__).warning(
            "Realtime channel unavailable; HTTP recovery remains available"
        )


def change(task, run, status, error="", error_type=""):
    if status not in TRANSITIONS.get(run.status, set()):
        raise ValidationError(f"无效状态流转 {run.status} → {status}")
    run.status = task.status = status
    if status in {Status.SUCCEEDED, Status.FAILED, Status.CANCELLED}:
        run.finished_at = timezone.now()
        run.duration = (
            (run.finished_at - run.started_at).total_seconds() if run.started_at else 0
        )
    if status == Status.RUNNING and not run.started_at:
        run.started_at = timezone.now()
    run.error_message = redact(error)
    run.error_type = error_type
    run.save()
    task.save(update_fields=["status", "updated_at"])
    transaction.on_commit(lambda: emit(task.id))


@transaction.atomic
def enqueue(task_id, user):
    task = Task.objects.select_for_update().get(id=task_id, user=user)
    last = task.runs.first()
    if last and last.status in ACTIVE:
        raise ValidationError("任务已排队或正在执行")
    if last and last.attempt_number >= 5:
        raise ValidationError("已达到五次受控执行上限，请创建新任务")
    # Never replay an approved external side effect on rerun.
    if Approval.objects.filter(task=task, consumed_at__isnull=False).exists():
        raise ValidationError("已有消费的审批，禁止重放外部副作用")
    run = TaskRun.objects.create(
        task=task,
        attempt_number=(last.attempt_number + 1 if last else 1),
        engine="mock" if task.model_name == "mock" else "browser-use",
    )
    task.status = Status.PENDING
    task.save()
    transaction.on_commit(lambda: dispatch(run.id))
    return run


def dispatch(run_id):
    from django.conf import settings

    if settings.LOCAL_DEMO_RUNNER:
        TaskRun.objects.filter(id=run_id).update(celery_task_id="local-demo-polling")
        return
    from .worker import execute

    try:
        job = execute.apply_async(args=[str(run_id)], task_id=str(run_id))
        TaskRun.objects.filter(id=run_id).update(celery_task_id=job.id)
    except Exception:
        with transaction.atomic():
            run = (
                TaskRun.objects.select_for_update()
                .select_related("task")
                .get(id=run_id)
            )
            if run.status == Status.PENDING:
                change(
                    run.task,
                    run,
                    Status.FAILED,
                    "队列不可用，请检查 Redis 和 Worker",
                    "QueueUnavailable",
                )


@transaction.atomic
def cancel(task_id, user):
    task = Task.objects.select_for_update().get(id=task_id, user=user)
    run = task.runs.first()
    if not run or run.status not in ACTIVE:
        raise ValidationError("没有可取消的执行")
    change(task, run, Status.CANCELLED)
    Approval.objects.filter(task_run=run, status="PENDING").update(
        status="REJECTED", reviewed_at=timezone.now(), reviewer=user
    )
    return task


@transaction.atomic
def step(run_id, action, parameters=None, url="", duration=0, error="", screenshot=""):
    run = TaskRun.objects.select_for_update().get(id=run_id)
    if run.status != Status.RUNNING:
        raise InterruptedError("执行已停止")
    if run.step_count >= run.task.max_steps:
        raise ValueError("达到最大执行步骤")
    run.step_count += 1
    run.save(update_fields=["step_count"])
    TaskStep.objects.create(
        task_run=run,
        step_number=run.step_count,
        action_name=action,
        action_parameters=redact(parameters or {}),
        page_url=redact(url),
        duration=duration,
        error_message=redact(error),
        status="FAILED" if error else "SUCCEEDED",
        screenshot_path=screenshot,
    )
    transaction.on_commit(lambda: emit(run.task_id, "step"))


@transaction.atomic
def request_approval(run_id, payload):
    run = TaskRun.objects.select_for_update().select_related("task").get(id=run_id)
    if run.status != Status.RUNNING:
        raise InterruptedError("任务已停止")
    approval = Approval.objects.create(
        task=run.task,
        task_run=run,
        operation_type="submit_form",
        operation_summary=redact(payload),
        payload=payload,
        fingerprint=fingerprint(payload),
    )
    change(run.task, run, Status.WAITING_APPROVAL)
    return approval


@transaction.atomic
def review(approval_id, user, approved):
    approval = (
        Approval.objects.select_for_update()
        .select_related("task", "task_run")
        .get(id=approval_id, task__user=user)
    )
    run = TaskRun.objects.select_for_update().get(id=approval.task_run_id)
    task = Task.objects.select_for_update().get(id=approval.task_id)
    if approval.status != "PENDING" or run.status != Status.WAITING_APPROVAL:
        raise ValidationError("审批已处理或执行已失效")
    if timezone.now() - approval.created_at > timezone.timedelta(hours=24):
        raise ValidationError("审批已过期，请取消任务")
    approval.status = "APPROVED" if approved else "REJECTED"
    approval.reviewer = user
    approval.reviewed_at = timezone.now()
    approval.save()
    change(task, run, Status.PENDING if approved else Status.CANCELLED)
    if approved:
        transaction.on_commit(lambda: dispatch(run.id))
    return approval
