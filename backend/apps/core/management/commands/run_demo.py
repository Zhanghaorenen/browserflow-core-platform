"""Local-only background runner for machines without Redis. Not a Celery substitute in deployment."""

import time
from django.core.management.base import BaseCommand
from apps.core.models import TaskRun, Status
from apps.core.worker import execute, recover_expired


class Command(BaseCommand):
    help = (
        "Local demo polling worker, marked explicitly; production uses Celery + Redis"
    )

    def handle(self, *args, **kwargs):
        self.stdout.write(
            "LOCAL DEMO runner: database polling; use Celery + Redis in deployment"
        )
        while True:
            for run_id in TaskRun.objects.filter(status=Status.PENDING).values_list(
                "id", flat=True
            ):
                execute.run(str(run_id))
            recover_expired.run()
            time.sleep(1)
