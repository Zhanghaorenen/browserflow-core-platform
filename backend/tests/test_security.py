import pytest
from unittest.mock import patch
from apps.core.security import validate_url, redact
from apps.core.agent import validate_output


@pytest.mark.parametrize(
    "url,domains",
    [
        ("file:///etc/passwd", ["example.com"]),
        ("http://localhost", ["localhost"]),
        ("http://127.0.0.1", ["127.0.0.1"]),
        ("http://169.254.169.254", ["169.254.169.254"]),
        ("http://10.0.0.1", ["10.0.0.1"]),
        ("http://[::1]", ["::1"]),
        ("http://user:pass@example.com", ["example.com"]),
        ("https://evil.com", ["example.com"]),
        ("http://example.com:8081", ["example.com"]),
        ("http://foo.internal", ["foo.internal"]),
    ],
)
def test_block_unsafe_addresses(url, domains, settings):
    settings.ALLOW_DEMO = False
    with pytest.raises(ValueError):
        validate_url(url, domains)


def test_dns_rebinding_blocked(settings):
    settings.ALLOW_DEMO = False
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 443))]):
        with pytest.raises(ValueError):
            validate_url("https://example.com", ["example.com"])


def test_exact_demo_exception(settings):
    settings.ALLOW_DEMO = True
    assert validate_url("http://127.0.0.1:8090/products", ["127.0.0.1"])
    with pytest.raises(ValueError):
        validate_url("http://127.0.0.1:8000/admin", ["127.0.0.1"])


def test_schema_validation(settings):
    settings.ALLOW_DEMO = True
    with pytest.raises(Exception):
        validate_output(
            {"items": [], "source_urls": ["http://127.0.0.1:8090"]}, {}, ["127.0.0.1"]
        )
    with pytest.raises(Exception):
        validate_output(
            {"items": [{"name": None}], "source_urls": ["http://127.0.0.1:8090"]},
            {},
            ["127.0.0.1"],
        )


def test_nested_redaction():
    assert redact({"nested": [{"api_key": "secret"}]}) == {
        "nested": [{"api_key": "[REDACTED]"}]
    }
