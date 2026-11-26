import pytest
from unittest.mock import patch
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from apps.core.models import Task, TaskRun, TaskResult, Status, Approval
from apps.core import services
from apps.core.security import fingerprint

pytestmark = pytest.mark.django_db


def test_auth_register_login_logout():
    c = APIClient()
    r = c.post(
        "/api/v1/auth/register/",
        {
            "username": "newuser",
            "password": "LongExample!123",
            "email": "test@example.com",
        },
    )
    assert r.status_code == 201
    r = c.post(
        "/api/v1/auth/login/", {"username": "newuser", "password": "LongExample!123"}
    )
    assert r.status_code == 200
    assert (
        c.post(
            "/api/v1/auth/login/",
            {"username": "test@example.com", "password": "LongExample!123"},
        ).status_code
        == 200
    )
    c.credentials(HTTP_AUTHORIZATION="Bearer " + r.data["access"])
    refresh = r.data["refresh"]
    assert c.get("/api/v1/auth/me/").data["username"] == "newuser"
    assert c.post("/api/v1/auth/logout/", {"refresh": refresh}).status_code == 200
    assert c.post("/api/v1/auth/refresh/", {"refresh": refresh}).status_code == 401


def test_password_change(client, user):
    assert (
        client.post(
            "/api/v1/auth/password/",
            {"old_password": "bad", "new_password": "GoodExample!123"},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/v1/auth/password/",
            {"old_password": "LongExample!123", "new_password": "GoodExample!123"},
        ).status_code
        == 200
    )
    user.refresh_from_db()
    assert user.check_password("GoodExample!123")


def test_anonymous_denied():
    assert APIClient().get("/api/v1/tasks/").status_code == 401


def test_create_and_filter(client, settings):
    settings.ALLOW_DEMO = True
    payload = {
        "name": "collect",
        "description": "Collect rows",
        "target_url": "http://127.0.0.1:8090/products",
        "allowed_domains": ["127.0.0.1"],
        "model_name": "mock",
    }
    r = client.post("/api/v1/tasks/", payload, format="json")
    assert r.status_code == 201
    assert client.get("/api/v1/tasks/?search=collect").data["count"] == 1
    assert client.get("/api/v1/tasks/?search=other").data["count"] == 0
    assert client.delete("/api/v1/tasks/" + str(r.data["id"]) + "/").status_code == 204


@pytest.mark.parametrize(
    "endpoint", ["", "runs/", "steps/", "result/", "run/", "cancel/"]
)
def test_task_isolation(client, task, endpoint):
    other = User.objects.create_user("other")
    task.user = other
    task.save()
    method = client.post if endpoint in ["run/", "cancel/"] else client.get
    assert method(f"/api/v1/tasks/{task.id}/{endpoint}").status_code == 404


def test_queue_unavailable_marks_failed(task):
    with patch("apps.core.worker.execute.apply_async", side_effect=ConnectionError()):
        run = TaskRun.objects.create(task=task, attempt_number=1)
        services.dispatch(run.id)
    run.refresh_from_db()
    assert run.status == "FAILED"
    assert run.error_type == "QueueUnavailable"


def test_duplicate_enqueue(task, user):
    with patch("apps.core.services.dispatch"):
        services.enqueue(task.id, user)
        with pytest.raises(Exception):
            services.enqueue(task.id, user)
    assert task.runs.count() == 1


def test_cancel_and_invalid_transition(task, user):
    run = TaskRun.objects.create(task=task, attempt_number=1)
    services.cancel(task.id, user)
    run.refresh_from_db()
    assert run.status == "CANCELLED"
    with pytest.raises(Exception):
        services.change(task, run, Status.SUCCEEDED)


def test_approval_review_replay(task, user):
    run = TaskRun.objects.create(task=task, attempt_number=1, status="RUNNING")
    a = services.request_approval(
        run.id, {"url": task.target_url, "fields": {"reason": "demo"}}
    )
    task.refresh_from_db()
    assert task.status == "WAITING_APPROVAL"
    with patch("apps.core.services.dispatch"):
        services.review(a.id, user, True)
    run.refresh_from_db()
    assert run.status == "PENDING"
    with pytest.raises(Exception):
        services.review(a.id, user, True)


def test_reject_stops_run(task, user):
    run = TaskRun.objects.create(task=task, attempt_number=1, status="RUNNING")
    a = services.request_approval(run.id, {"fields": {}})
    services.review(a.id, user, False)
    run.refresh_from_db()
    assert run.status == "CANCELLED"


def test_consumed_approval_cannot_rerun(task, user):
    from django.utils import timezone

    run = TaskRun.objects.create(task=task, attempt_number=1, status="FAILED")
    Approval.objects.create(
        task=task,
        task_run=run,
        operation_type="submit",
        operation_summary={},
        payload={},
        fingerprint=fingerprint({}),
        status="APPROVED",
        consumed_at=timezone.now(),
    )
    with pytest.raises(Exception):
        services.enqueue(task.id, user)


def test_step_redaction_and_budget(task):
    task.max_steps = 1
    task.save()
    run = TaskRun.objects.create(task=task, attempt_number=1, status="RUNNING")
    services.step(run.id, "tool", {"password": "secret", "nested": {"token": "secret"}})
    step = run.steps.get()
    assert step.action_parameters["password"] == "[REDACTED]"
    with pytest.raises(ValueError):
        services.step(run.id, "tool")


def test_export_csv_and_isolation(client, task):
    run = TaskRun.objects.create(task=task, attempt_number=1, status="SUCCEEDED")
    result = TaskResult.objects.create(
        task_run=run,
        raw_result="raw",
        structured_result={"items": [{"name": "=DANGEROUS()", "price": "100"}]},
        validation_status="VALID",
    )
    response = client.get(f"/api/v1/results/{result.id}/export/?format_type=csv")
    assert response.status_code == 200
    assert "'=DANGEROUS()" in response.content.decode()
    assert (
        client.get(f"/api/v1/results/{result.id}/export/?format_type=json").status_code
        == 200
    )
    task.user = User.objects.create_user("other")
    task.save()
    assert client.get(f"/api/v1/results/{result.id}/export/").status_code == 404


def test_statistics_no_fake_data(client, task):
    data = client.get("/api/v1/dashboard/summary/").data
    assert data["total"] == 1
    assert data["counts"]["SUCCEEDED"] == 0
    assert data["success_rate"] == 0


def test_preferences_validation(client):
    assert (
        client.patch(
            "/api/v1/system/preferences/", {"max_steps": 999}, format="json"
        ).status_code
        == 400
    )
    assert (
        client.patch(
            "/api/v1/system/preferences/", {"theme": "dark"}, format="json"
        ).data["theme"]
        == "dark"
    )


def test_seed_templates_read_only(client):
    from django.core.management import call_command

    call_command("seed_templates")
    call_command("seed_templates")
    rows = client.get("/api/v1/templates/").data["results"]
    assert len(rows) == 3
    assert (
        client.delete("/api/v1/templates/" + str(rows[0]["id"]) + "/").status_code
        == 403
    )


def test_worker_lease_recovery(task):
    from django.utils import timezone
    from datetime import timedelta
    from apps.core.worker import recover_expired

    run = TaskRun.objects.create(
        task=task,
        attempt_number=1,
        status="RUNNING",
        started_at=timezone.now() - timedelta(hours=1),
    )
    recover_expired()
    run.refresh_from_db()
    assert run.status == "FAILED"
    assert run.error_type == "WorkerLeaseExpired"
