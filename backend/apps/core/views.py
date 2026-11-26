import csv, io, json
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.db.models import Q, Count, Avg
from django.db.models.functions import TruncDate
from django.http import HttpResponse, FileResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework_simplejwt.tokens import RefreshToken
from .models import *
from .serializers import *
from . import services


@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    s = RegisterSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    u = s.save()
    return Response(UserSerializer(u).data, status=201)


@api_view(["GET", "PATCH"])
def me(request):
    s = (
        UserSerializer(request.user, data=request.data, partial=True)
        if request.method == "PATCH"
        else UserSerializer(request.user)
    )
    if request.method == "PATCH":
        s.is_valid(raise_exception=True)
        s.save()
    return Response(s.data)


@api_view(["POST"])
def password(request):
    if not request.user.check_password(request.data.get("old_password", "")):
        raise ValidationError("原密码不正确")
    new = request.data.get("new_password", "")
    validate_password(new, request.user)
    request.user.set_password(new)
    request.user.save()
    return Response({"changed": True})


@api_view(["POST"])
def logout(request):
    try:
        token = RefreshToken(request.data.get("refresh", ""))
        if str(token["user_id"]) != str(request.user.id):
            raise PermissionDenied()
        token.blacklist()
    except PermissionDenied:
        raise
    except Exception:
        raise ValidationError("Refresh Token 无效")
    return Response({"logged_out": True})


class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        q = Task.objects.filter(user=self.request.user).prefetch_related("runs")
        if self.request.query_params.get("search"):
            q = q.filter(name__icontains=self.request.query_params["search"])
        if self.request.query_params.get("status"):
            q = q.filter(status=self.request.query_params["status"])
        for key, lookup in [
            ("after", "created_at__date__gte"),
            ("before", "created_at__date__lte"),
        ]:
            if self.request.query_params.get(key):
                q = q.filter(**{lookup: self.request.query_params[key]})
        return q

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_destroy(self, obj):
        if obj.runs.filter(status__in=services.ACTIVE).exists():
            raise ValidationError("请先取消正在执行的任务")
        obj.delete()

    @action(detail=True, methods=["post"])
    def run(self, request, pk=None):
        obj = self.get_object()
        run = services.enqueue(obj.id, request.user)
        return Response(RunSerializer(run).data, status=202)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return Response(
            TaskSerializer(services.cancel(self.get_object().id, request.user)).data
        )

    @action(detail=True)
    def runs(self, request, pk=None):
        return Response(RunSerializer(self.get_object().runs.all(), many=True).data)

    @action(detail=True)
    def steps(self, request, pk=None):
        obj = self.get_object()
        run_id = request.query_params.get("run")
        run = get_object_or_404(obj.runs, id=run_id) if run_id else obj.runs.first()
        return Response(StepSerializer(run.steps.all(), many=True).data if run else [])

    @action(detail=True)
    def result(self, request, pk=None):
        result = (
            TaskResult.objects.filter(task_run__task=self.get_object())
            .order_by("-created_at")
            .first()
        )
        return Response(ResultSerializer(result).data if result else None)

    @action(detail=True, url_path="screenshots/(?P<step_id>[0-9]+)")
    def screenshot(self, request, pk=None, step_id=None):
        step = get_object_or_404(TaskStep, pk=step_id, task_run__task=self.get_object())
        path = (settings.MEDIA_ROOT / step.screenshot_path).resolve()
        if (
            not step.screenshot_path
            or not path.is_relative_to(settings.MEDIA_ROOT.resolve())
            or not path.is_file()
        ):
            raise ValidationError("截图不存在")
        return FileResponse(path.open("rb"), content_type="image/png")


class TemplateViewSet(viewsets.ModelViewSet):
    serializer_class = TemplateSerializer

    def get_queryset(self):
        return TaskTemplate.objects.filter(
            Q(owner=self.request.user) | Q(owner__isnull=True)
        ).order_by("id")

    def perform_create(self, s):
        s.save(owner=self.request.user)

    def perform_update(self, s):
        if s.instance.owner_id != self.request.user.id:
            raise PermissionDenied("内置模板只读")
        s.save()

    def perform_destroy(self, obj):
        if obj.owner_id != self.request.user.id:
            raise PermissionDenied("内置模板只读")
        obj.delete()


class ApprovalViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ApprovalSerializer

    @action(detail=False)
    def summary(self, request):
        return Response(
            {
                status: self.get_queryset().filter(status=status).count()
                for status in ["PENDING", "APPROVED", "REJECTED"]
            }
        )

    def get_queryset(self):
        return Approval.objects.filter(task__user=self.request.user).select_related(
            "task"
        )

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return Response(
            ApprovalSerializer(
                services.review(self.get_object().id, request.user, True)
            ).data
        )

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return Response(
            ApprovalSerializer(
                services.review(self.get_object().id, request.user, False)
            ).data
        )


class ResultViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ResultSerializer

    def get_queryset(self):
        q = (
            TaskResult.objects.filter(task_run__task__user=self.request.user)
            .select_related("task_run__task")
            .order_by("-created_at")
        )
        if self.request.query_params.get("search"):
            q = q.filter(
                task_run__task__name__icontains=self.request.query_params["search"]
            )
        return q

    @action(detail=True)
    def export(self, request, pk=None):
        obj = self.get_object()
        fmt = request.query_params.get("format_type", "json")
        from .exports import render_result

        text, mime = render_result(obj.structured_result, fmt)
        response = HttpResponse(text, content_type=mime + "; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="result-{obj.id}.{fmt}"'
        )
        return response


@api_view(["GET"])
def summary(request):
    tasks = Task.objects.filter(user=request.user)
    runs = TaskRun.objects.filter(task__user=request.user)
    counts = {s: tasks.filter(status=s).count() for s in Status.values}
    finished = counts["SUCCEEDED"] + counts["FAILED"]
    metrics = runs.filter(finished_at__isnull=False).aggregate(
        average_duration=Avg("duration"), average_steps=Avg("step_count")
    )
    usage = [
        u for u in runs.values_list("usage", flat=True) if u and "total_tokens" in u
    ]
    return Response(
        {
            "total": tasks.count(),
            "counts": counts,
            "success_rate": round(100 * counts["SUCCEEDED"] / finished, 1)
            if finished
            else 0,
            **metrics,
            "model_usage": {
                "total_tokens": sum(u["total_tokens"] for u in usage),
                "reported_runs": len(usage),
            }
            if usage
            else None,
            "recent": TaskSerializer(tasks[:5], many=True).data,
            "failures": RunSerializer(runs.filter(status="FAILED")[:5], many=True).data,
        }
    )


@api_view(["GET"])
def trends(request):
    rows = (
        Task.objects.filter(
            user=request.user, created_at__gte=timezone.now() - timedelta(days=7)
        )
        .annotate(date=TruncDate("created_at"))
        .values("date", "status")
        .annotate(count=Count("id"))
        .order_by("date")
    )
    return Response(list(rows))


@api_view(["GET"])
def errors(request):
    return Response(
        list(
            TaskRun.objects.filter(task__user=request.user, status="FAILED")
            .values("error_type")
            .annotate(count=Count("id"))
        )
    )


@api_view(["GET", "PATCH"])
def preferences(request):
    p, _ = Preferences.objects.get_or_create(user=request.user)
    s = (
        PreferencesSerializer(p, data=request.data, partial=True)
        if request.method == "PATCH"
        else PreferencesSerializer(p)
    )
    if request.method == "PATCH":
        s.is_valid(raise_exception=True)
        s.save()
    return Response(s.data)


@api_view(["GET"])
def health(request):
    from django.db import connection
    import redis

    database = redis_ok = False
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            database = True
    except Exception:
        pass
    try:
        redis_ok = redis.Redis.from_url(
            settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1
        ).ping()
    except Exception:
        pass
    from config.celery import app

    try:
        workers = (
            list((app.control.inspect(timeout=1).ping() or {}).keys())
            if redis_ok
            else []
        )
    except Exception:
        workers = []
    return Response(
        {
            "version": "1.0.0",
            "database": database,
            "redis": redis_ok,
            "workers": workers,
            "queued": Task.objects.filter(user=request.user, status="PENDING").count(),
            "provider": settings.MODEL_PROVIDER,
            "runner_mode": "local-demo" if settings.LOCAL_DEMO_RUNNER else "celery",
            "model_configured": bool(settings.MODEL_API_KEY),
            "models": ["mock", settings.MODEL_NAME],
            "demo_origin": settings.DEMO_ORIGIN if settings.ALLOW_DEMO else None,
        }
    )


@api_view(["POST"])
def model_probe(request):
    import httpx

    if not settings.MODEL_API_KEY:
        return Response({"connected": False, "detail": "尚未配置服务端模型密钥"})
    try:
        r = httpx.get(
            settings.MODEL_BASE_URL.rstrip("/") + "/models",
            headers={"Authorization": f"Bearer {settings.MODEL_API_KEY}"},
            timeout=10,
        )
        return Response({"connected": r.is_success, "http_status": r.status_code})
    except Exception:
        return Response({"connected": False, "detail": "模型端点连接失败"})
