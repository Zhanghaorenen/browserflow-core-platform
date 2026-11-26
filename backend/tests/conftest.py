import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient


@pytest.fixture
def user(db):
    return User.objects.create_user(username="tester", password="LongExample!123")


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def task(user):
    from apps.core.models import Task

    return Task.objects.create(
        user=user,
        name="Test task",
        description="Collect products",
        target_url="http://127.0.0.1:8090/products",
        allowed_domains=["127.0.0.1"],
    )
