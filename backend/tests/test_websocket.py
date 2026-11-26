import pytest
from channels.testing import WebsocketCommunicator
from rest_framework_simplejwt.tokens import RefreshToken
from asgiref.sync import sync_to_async
from apps.core.consumer import TaskConsumer
from apps.core.services import emit


@pytest.mark.django_db(transaction=True)
async def test_websocket_auth_ownership_and_event(user, task):
    token = await sync_to_async(lambda: str(RefreshToken.for_user(user).access_token))()
    app = TaskConsumer.as_asgi()
    c = WebsocketCommunicator(app, f"/ws/tasks/{task.id}/")
    c.scope["url_route"] = {"kwargs": {"task_id": task.id}}
    ok, _ = await c.connect()
    assert ok
    await c.send_json_to({"token": token})
    assert (await c.receive_json_from())["event"] == "connected"
    await sync_to_async(emit)(task.id, "step")
    assert (await c.receive_json_from())["event"] == "step"
    await c.disconnect()
    from django.contrib.auth.models import User

    other = await sync_to_async(User.objects.create_user)("outsider")
    token = await sync_to_async(
        lambda: str(RefreshToken.for_user(other).access_token)
    )()
    c = WebsocketCommunicator(app, "/")
    c.scope["url_route"] = {"kwargs": {"task_id": task.id}}
    await c.connect()
    await c.send_json_to({"token": token})
    assert (await c.receive_output())["code"] == 4403
    await c.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_websocket_invalid_token(task):
    c = WebsocketCommunicator(TaskConsumer.as_asgi(), "/")
    c.scope["url_route"] = {"kwargs": {"task_id": task.id}}
    await c.connect()
    await c.send_json_to({"token": "invalid"})
    assert (await c.receive_output())["code"] == 4401
    await c.disconnect()
