import asyncio, json
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from rest_framework_simplejwt.tokens import AccessToken
from .models import Task


class TaskConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.authorized = False
        await self.accept()
        self.auth_timeout = asyncio.create_task(self.expire_auth())

    async def expire_auth(self):
        await asyncio.sleep(5)
        if not self.authorized:
            await self.close(code=4401)

    async def receive_json(self, content, **kwargs):
        if self.authorized:
            return
        try:
            token = await database_sync_to_async(AccessToken)(content.get("token", ""))
            self.expires = token["exp"]
            task_id = self.scope["url_route"]["kwargs"]["task_id"]
            exists = await database_sync_to_async(
                Task.objects.filter(
                    id=task_id, user_id=token["user_id"], user__is_active=True
                ).exists
            )()
            if not exists:
                await self.close(code=4403)
                return
            self.group = f"task.{task_id}"
            self.authorized = True
            self.auth_timeout.cancel()
            await self.channel_layer.group_add(self.group, self.channel_name)
            await self.send_json({"event": "connected", "task_id": str(task_id)})
            self.token_timer = asyncio.create_task(self.expire_token())
            from django.conf import settings

            if settings.LOCAL_DEMO_RUNNER:
                self.local_timer = asyncio.create_task(self.local_events(task_id))
        except Exception:
            await self.close(code=4401)

    async def local_events(self, task_id):
        # Redis-free demo only: production uses channel-layer events from Celery.
        previous = None
        while True:
            from .models import TaskRun

            current = await database_sync_to_async(
                lambda: list(
                    TaskRun.objects.filter(task_id=task_id).values_list(
                        "status", "step_count"
                    )
                )
            )()
            if current != previous:
                await self.send_json(
                    {
                        "event": "updated",
                        "transport": "local-db-poll",
                        "task_id": str(task_id),
                    }
                )
                previous = current
            await asyncio.sleep(1)

    async def expire_token(self):
        import time

        await asyncio.sleep(max(0, self.expires - time.time()))
        await self.close(code=4401)

    async def task_event(self, event):
        await self.send_json(event)

    async def disconnect(self, code):
        if hasattr(self, "auth_timeout"):
            self.auth_timeout.cancel()
        if hasattr(self, "token_timer"):
            self.token_timer.cancel()
        if hasattr(self, "local_timer"):
            self.local_timer.cancel()
        if self.authorized:
            await self.channel_layer.group_discard(self.group, self.channel_name)
