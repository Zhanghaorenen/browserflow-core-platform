"""24 repeatable Chromium acceptance cases, using an isolated fixture server."""

import asyncio, importlib.util, json, threading
from pathlib import Path
from unittest.mock import patch
import pytest
from apps.core.models import TaskRun, Approval, Status, TaskResult
from apps.core.worker import execute, execute_async, claim, run_browser_coroutine
from apps.core import services
from apps.core.agent import BrowserAgentService


@pytest.fixture(scope="module")
def demo():
    spec = importlib.util.spec_from_file_location(
        "demo_server", Path(__file__).resolve().parents[2] / "demo-sites" / "server.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    module.init()
    server = module.ThreadingHTTPServer(("127.0.0.1", 0), module.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


@pytest.fixture
def prepared(task, settings, demo):
    settings.ALLOW_DEMO = True
    settings.DEMO_ORIGIN = demo
    task.target_url = demo + "/products"
    task.parameters = {"limit": 5}
    task.save()
    return task


def run_task(task):
    run = TaskRun.objects.create(task=task, attempt_number=task.runs.count() + 1)
    execute.run(str(run.id))
    run.refresh_from_db()
    return run


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("limit", [1, 2, 3, 4, 5])
def test_public_catalog(prepared, limit):
    prepared.parameters = {"limit": limit}
    prepared.save()
    run = run_task(prepared)
    assert run.status == "SUCCEEDED", run.error_message
    assert len(run.result.structured_result["items"]) == limit
    assert run.result.structured_result["items"][0]["name"] == "Cloud Console"
    from django.conf import settings

    assert (settings.MEDIA_ROOT / run.result.file_path).is_file()
    assert run.steps.filter(screenshot_path__gt="").exists()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("limit", [1, 3, 5])
def test_dynamic_catalog(prepared, demo, limit):
    prepared.target_url = demo + "/dynamic"
    prepared.parameters = {"limit": limit}
    prepared.save()
    run = run_task(prepared)
    assert run.status == "SUCCEEDED", run.error_message
    assert len(run.result.structured_result["items"]) == limit
    assert run.result.structured_result["items"][0]["name"] == "Dynamic Software 1"


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("path", ["/products", "/dynamic"])
def test_multiple_pages(prepared, demo, path):
    prepared.target_url = demo + path
    prepared.parameters = {"multi_page": True, "limit": 10}
    prepared.save()
    run = run_task(prepared)
    assert run.status == "SUCCEEDED", run.error_message
    assert len(run.result.structured_result["items"]) == 10


def form_task(task, demo):
    task.target_url = demo + "/form"
    task.parameters = {
        "fields": {
            "applicant": "测试申请人",
            "department": "研发部",
            "reason": "集成测试",
        }
    }
    task.save()


@pytest.mark.django_db(transaction=True)
def test_approval_submit(prepared, user, demo):
    form_task(prepared, demo)
    run = run_task(prepared)
    assert run.status == "WAITING_APPROVAL", run.error_message
    assert not TaskResult.objects.filter(task_run=run).exists()
    a = run.approvals.get()
    with patch("apps.core.services.dispatch"):
        services.review(a.id, user, True)
    execute.run(str(run.id))
    run.refresh_from_db()
    a.refresh_from_db()
    assert run.status == "SUCCEEDED", run.error_message
    assert a.consumed_at
    assert run.result.structured_result["items"][0]["receipt"]


@pytest.mark.django_db(transaction=True)
def test_approval_reject(prepared, user, demo):
    form_task(prepared, demo)
    run = run_task(prepared)
    assert run.status == "WAITING_APPROVAL", run.error_message
    services.review(run.approvals.get().id, user, False)
    execute.run(str(run.id))
    run.refresh_from_db()
    assert run.status == "CANCELLED"
    assert not run.approvals.get().consumed_at


@pytest.mark.django_db(transaction=True)
def test_approval_tamper(prepared, user, demo):
    form_task(prepared, demo)
    run = run_task(prepared)
    assert run.status == "WAITING_APPROVAL", run.error_message
    a = run.approvals.get()
    with patch("apps.core.services.dispatch"):
        services.review(a.id, user, True)
    a.payload["fields"]["reason"] = "tampered"
    a.save(update_fields=["payload"])
    execute.run(str(run.id))
    run.refresh_from_db()
    assert run.status == "FAILED"
    assert "变更" in run.error_message
    assert not run.approvals.get().consumed_at


@pytest.mark.django_db(transaction=True)
def test_consumed_approval_replay(prepared, user, demo):
    from django.utils import timezone

    form_task(prepared, demo)
    run = run_task(prepared)
    assert run.status == "WAITING_APPROVAL", run.error_message
    a = run.approvals.get()
    with patch("apps.core.services.dispatch"):
        services.review(a.id, user, True)
    a.consumed_at = timezone.now()
    a.save(update_fields=["consumed_at"])
    execute.run(str(run.id))
    run.refresh_from_db()
    assert run.status == "FAILED"
    assert "不可消费" in run.error_message


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("path", ["/empty", "/missing"])
def test_incomplete_results_fail(prepared, demo, path):
    prepared.target_url = demo + path
    prepared.save()
    run = run_task(prepared)
    assert run.status == "FAILED"
    assert not TaskResult.objects.filter(task_run=run).exists()


@pytest.mark.django_db(transaction=True)
def test_schema_business_validation(prepared):
    prepared.output_schema = {
        "type": "object",
        "properties": {"items": {"type": "array", "minItems": 6}},
    }
    prepared.save()
    run = run_task(prepared)
    assert run.status == "FAILED"


@pytest.mark.django_db(transaction=True)
def test_step_budget(prepared):
    prepared.max_steps = 1
    prepared.save()
    run = run_task(prepared)
    assert run.status == "FAILED"
    assert run.step_count == 1


@pytest.mark.django_db(transaction=True)
def test_timeout(prepared, demo):
    prepared.target_url = demo + "/slow"
    prepared.timeout_seconds = 1
    prepared.save()
    run = run_task(prepared)
    assert run.status == "FAILED"
    assert run.error_type == "TimeoutError"


@pytest.mark.django_db(transaction=True)
def test_redirect_private_blocked(prepared, demo):
    prepared.target_url = demo + "/redirect"
    prepared.save()
    run = run_task(prepared)
    assert run.status == "FAILED"


@pytest.mark.django_db(transaction=True)
def test_allowlist_enforced(prepared):
    prepared.allowed_domains = ["example.com"]
    prepared.save()
    run = run_task(prepared)
    assert run.status == "FAILED"
    assert "白名单" in run.error_message


@pytest.mark.django_db(transaction=True)
def test_live_cancellation(prepared, demo):
    from asgiref.sync import sync_to_async

    prepared.target_url = demo + "/slow"
    prepared.save()
    run = TaskRun.objects.create(task=prepared, attempt_number=1)
    config, approved = claim(run.id)

    async def scenario():
        work = asyncio.create_task(execute_async(str(run.id), config, approved))
        await asyncio.sleep(0.8)
        await sync_to_async(
            lambda: TaskRun.objects.filter(id=run.id).update(status="CANCELLED")
        )()
        with pytest.raises(InterruptedError):
            await work

    run_browser_coroutine(scenario())


@pytest.mark.django_db(transaction=True)
def test_browser_use_sdk_with_scripted_model(prepared):
    from browser_use.llm.views import ChatInvokeCompletion

    class ScriptedModel:
        model = "fixture-model"
        provider = "fixture"
        name = "fixture"
        model_name = "fixture"
        _verified_api_keys = True

        def __init__(self):
            self.index = 0

        async def ainvoke(self, messages, output_format=None, **kwargs):
            actions = [
                {"navigate": {"url": prepared.target_url, "new_tab": False}},
                {"save_structured_data": {}},
                {"validate_extraction": {}},
                {
                    "done": {
                        "text": "Data saved and independently validated",
                        "success": True,
                    }
                },
            ]
            action = actions[min(self.index, len(actions) - 1)]
            self.index += 1
            payload = {
                "evaluation_previous_goal": "Fixture step",
                "memory": "Scripted test model, no real inference",
                "next_goal": "Execute next fixture action",
                "action": [action],
            }
            return ChatInvokeCompletion(
                completion=output_format.model_validate(payload), usage=None
            )

    config = {
        k: getattr(prepared, k)
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
    config["model_name"] = "fixture-model"
    config["run_id"] = "sdk-fixture"
    logs = []
    adapter = BrowserAgentService(
        config, lambda *a, **kw: logs.append((a, kw)), llm=ScriptedModel()
    )
    result = run_browser_coroutine(asyncio.wait_for(adapter.run(), 90))
    assert len(result["items"]) == 5
    assert logs


@pytest.mark.django_db(transaction=True)
def test_missing_model_credentials_fail(prepared, settings):
    settings.MODEL_API_KEY = ""
    prepared.model_name = "gpt-4.1-mini"
    prepared.save()
    run = run_task(prepared)
    assert run.status == "FAILED"
    assert "API Key" in run.error_message
