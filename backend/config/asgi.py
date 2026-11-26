import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from django.core.asgi import get_asgi_application

django_app = get_asgi_application()
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.urls import path
from apps.core.consumer import TaskConsumer

application = ProtocolTypeRouter(
    {
        "http": django_app,
        "websocket": AllowedHostsOriginValidator(
            URLRouter([path("ws/tasks/<uuid:task_id>/", TaskConsumer.as_asgi())])
        ),
    }
)
