from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from apps.core import views as v
from apps.core.serializers import LoginSerializer

router = DefaultRouter()
for name, view in [
    ("tasks", v.TaskViewSet),
    ("templates", v.TemplateViewSet),
    ("approvals", v.ApprovalViewSet),
    ("results", v.ResultViewSet),
]:
    router.register(name, view, basename=name)
urlpatterns = [path("admin/", admin.site.urls), path("api/v1/", include(router.urls))]
for route, view in [
    ("auth/register", v.register),
    ("auth/login", TokenObtainPairView.as_view(serializer_class=LoginSerializer)),
    ("auth/refresh", TokenRefreshView.as_view()),
    ("auth/me", v.me),
    ("auth/logout", v.logout),
    ("auth/password", v.password),
    ("dashboard/summary", v.summary),
    ("dashboard/trends", v.trends),
    ("dashboard/errors", v.errors),
    ("system/health", v.health),
    ("system/preferences", v.preferences),
    ("system/model-probe", v.model_probe),
]:
    urlpatterns.append(path("api/v1/" + route + "/", view))
