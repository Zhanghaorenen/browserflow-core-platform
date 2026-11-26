import asyncio
import json
import sys
from celery import shared_task
from django.db import transaction, close_old_connections
from django.utils import timezone
from asgiref.sync import sync_to_async
from .models import TaskRun, Task, TaskResult, Approval, Status
from .agent import BrowserAgentService, ApprovalPending
from . import services


def run_browser_coroutine(coroutine):
    # Daphne installs a selector policy on Windows. Playwright needs a
    # proactor for its driver subprocess, so choose a loop for this run only.
    if sys.platform == "win32":
        with asyncio.Runner(loop_factory=asyncio.ProactorEventLoop) as runner:
            return runner.run(coroutine)
    return asyncio.run(coroutine)


@transaction.atomic
def claim(run_id):
    run = TaskRun.objects.select_for_update().select_related("task").get(id=run_id)
    if run.status != Status.PENDING:
        return None
    services.change(run.task, run, Status.RUNNING)
    task = run.task
    config = {
        k: getattr(task, k)
        for k in [
            "description",
            "target_url",
            "allowed_domains",
            "model_name",
            "max_steps",
            "timeout_seconds",
            "output_schema",
            "parameters",
        ]
    }
    config["run_id"] = str(run.id)
    approval = run.approvals.filter(status="APPROVED").first()
    approved = (
        {
            "id": str(approval.id),
            "payload": approval.payload,
            "fingerprint": approval.fingerprint,
        }
        if approval
        else None
    )
    return config, approved


@transaction.atomic
def consume(approval_id):
    approval = Approval.objects.select_for_update().get(id=approval_id)
    if (
        approval.status != "APPROVED"
        or approval.consumed_at
        or approval.task_run.status != Status.RUNNING
    ):
        raise ValueError("审批不可消费")
    approval.consumed_at = timezone.now()
    approval.save(update_fields=["consumed_at"])


async def execute_async(run_id, config, approved):
    adapter = BrowserAgentService(
        config,
        lambda *a, **kw: services.step(run_id, *a, **kw),
        approval=approved,
        request_approval=lambda payload: services.request_approval(run_id, payload),
        consume=consume,
    )

    async def watch():
        while True:
            await asyncio.sleep(0.3)
            status = await sync_to_async(
                lambda: TaskRun.objects.values_list("status", flat=True).get(id=run_id),
                thread_sensitive=True,
            )()
            if status == Status.CANCELLED:
                raise InterruptedError("用户取消任务")

    work = asyncio.create_task(adapter.run())
    monitor = asyncio.create_task(watch())
    try:
        done, _ = await asyncio.wait(
            [work, monitor],
            timeout=config["timeout_seconds"],
            return_when=asyncio.FIRST_COMPLETED,
        )
        if not done:
            raise TimeoutError("任务执行超时")
        if monitor in done:
            return await monitor
        result = await work
        return {
            "structured": result,
            "raw": adapter.raw_result or json.dumps(result, ensure_ascii=False),
            "usage": adapter.usage,
        }
    finally:
        work.cancel()
        monitor.cancel()
        await asyncio.gather(work, monitor, return_exceptions=True)


@shared_task(bind=True, soft_time_limit=930, time_limit=960, max_retries=0)
def execute(self, run_id):
    close_old_connections()
    claimed = claim(run_id)
    if not claimed:
        return
    config, approved = claimed
    try:
        result = run_browser_coroutine(execute_async(run_id, config, approved))
        with transaction.atomic():
            run = (
                TaskRun.objects.select_for_update()
                .select_related("task")
                .get(id=run_id)
            )
            if run.status != Status.RUNNING:
                return
            structured = result["structured"]
            from django.conf import settings
            from .exports import render_result

            content, _ = render_result(structured, run.task.output_type)
            output_path = (
                settings.MEDIA_ROOT / str(run.id) / ("result." + run.task.output_type)
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(content)
            TaskResult.objects.create(
                task_run=run,
                raw_result=result["raw"],
                structured_result=structured,
                source_urls=structured["source_urls"],
                validation_status="VALID",
                file_path=str(output_path.relative_to(settings.MEDIA_ROOT)),
            )
            run.usage = result["usage"]
            services.change(run.task, run, Status.SUCCEEDED)
    except ApprovalPending:
        pass
    except Exception as exc:
        with transaction.atomic():
            run = (
                TaskRun.objects.select_for_update()
                .select_related("task")
                .get(id=run_id)
            )
            if run.status in {Status.RUNNING, Status.PENDING}:
                services.change(
                    run.task, run, Status.FAILED, str(exc), type(exc).__name__
                )
    finally:
        close_old_connections()


@shared_task
def recover_expired():
    # Beat reconciles hard-killed workers; never automatically replays side effects.
    now = timezone.now()
    for run in TaskRun.objects.filter(
        status__in=[Status.RUNNING, Status.PENDING, Status.WAITING_APPROVAL]
    ).select_related("task"):
        expired = (
            (
                run.status == Status.RUNNING
                and run.started_at
                and (now - run.started_at).total_seconds()
                > run.task.timeout_seconds + 60
            )
            or (
                run.status == Status.PENDING
                and (now - run.task.updated_at).total_seconds() > 1200
            )
            or (
                run.status == Status.WAITING_APPROVAL
                and (now - run.task.updated_at).total_seconds() > 86400
            )
        )
        if expired:
            with transaction.atomic():
                locked = (
                    TaskRun.objects.select_for_update()
                    .select_related("task")
                    .get(id=run.id)
                )
                if locked.status == run.status:
                    services.change(
                        locked.task,
                        locked,
                        Status.FAILED,
                        "执行租约或审批已过期；请检查 Worker",
                        "WorkerLeaseExpired",
                    )
                    locked.approvals.filter(status="PENDING").update(
                        status="REJECTED", reviewed_at=now
                    )
