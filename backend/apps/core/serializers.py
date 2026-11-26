import re
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from django.conf import settings
from jsonschema import Draft202012Validator
from .models import (
    Task,
    TaskRun,
    TaskStep,
    TaskResult,
    TaskTemplate,
    Approval,
    Preferences,
)
from .security import validate_url
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class LoginSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        identifier = attrs.get("username", "")
        if "@" in identifier:
            matches = User.objects.filter(email__iexact=identifier)
            if matches.count() == 1:
                attrs["username"] = matches.get().username
        return super().validate(attrs)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name"]
        read_only_fields = ["id", "username"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def create(self, data):
        return User.objects.create_user(**data)


class TaskSerializer(serializers.ModelSerializer):
    latest_run = serializers.SerializerMethodField()

    class Meta:
        model = Task
        exclude = ["user"]
        read_only_fields = ["id", "status", "created_at", "updated_at"]

    def get_latest_run(self, obj):
        run = obj.runs.first()
        return RunSerializer(run).data if run else None

    def validate(self, data):
        domains = data.get("allowed_domains", [])
        if not domains or not isinstance(domains, list) or len(domains) > 20:
            raise serializers.ValidationError("请提供 1–20 个允许的精确域名")
        if any(
            not isinstance(d, str) or not re.fullmatch(r"[a-z0-9.-]+", d) or ".." in d
            for d in domains
        ):
            raise serializers.ValidationError(
                "白名单应为小写精确域名，不包含协议、端口或通配符"
            )
        if not 1 <= data.get("max_steps", 20) <= 100:
            raise serializers.ValidationError("步骤数范围为 1–100")
        if not 5 <= data.get("timeout_seconds", 120) <= 900:
            raise serializers.ValidationError("超时范围为 5–900 秒")
        if data.get("output_type", "json") not in ["json", "csv"]:
            raise serializers.ValidationError("输出格式应为 json 或 csv")
        if data.get("model_name", "mock") not in ["mock", settings.MODEL_NAME]:
            raise serializers.ValidationError("模型未在服务端配置")
        if data.get("target_url"):
            validate_url(data["target_url"], domains, resolve=False)
        schema = data.get("output_schema", {})
        try:
            Draft202012Validator.check_schema(schema)
        except Exception:
            raise serializers.ValidationError("结果 JSON Schema 无效")
        if len(str(data.get("parameters", {}))) > 20000:
            raise serializers.ValidationError("任务参数过大")
        return data


class RunSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskRun
        fields = "__all__"


class StepSerializer(serializers.ModelSerializer):
    task_id = serializers.UUIDField(source="task_run.task_id", read_only=True)
    run_id = serializers.UUIDField(source="task_run_id", read_only=True)

    class Meta:
        model = TaskStep
        fields = "__all__"


class ResultSerializer(serializers.ModelSerializer):
    task_id = serializers.UUIDField(source="task_run.task_id", read_only=True)
    task_name = serializers.CharField(source="task_run.task.name", read_only=True)
    engine = serializers.CharField(source="task_run.engine", read_only=True)

    class Meta:
        model = TaskResult
        fields = "__all__"


class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskTemplate
        fields = "__all__"
        read_only_fields = ["owner", "created_at"]


class ApprovalSerializer(serializers.ModelSerializer):
    task_name = serializers.CharField(source="task.name", read_only=True)

    class Meta:
        model = Approval
        exclude = ["payload", "fingerprint"]
        read_only_fields = ["status", "reviewer", "reviewed_at", "consumed_at"]


class PreferencesSerializer(serializers.ModelSerializer):
    max_steps = serializers.IntegerField(min_value=1, max_value=100)
    timeout_seconds = serializers.IntegerField(min_value=5, max_value=900)
    theme = serializers.ChoiceField(choices=["light", "dark"])

    class Meta:
        model = Preferences
        exclude = ["id", "user"]
