import hashlib, ipaddress, json, re, socket
from urllib.parse import urlsplit, urlunsplit
from django.conf import settings


def redact(value):
    if isinstance(value, dict):
        return {
            k: (
                "[REDACTED]"
                if re.search(
                    r"password|token|secret|api.?key|authorization|cookie", k, re.I
                )
                else redact(v)
            )
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        value = re.sub(r"(?i)(bearer\s+)[\w.\-]+", r"\1[REDACTED]", value)
        return re.sub(
            r"(?i)((?:api_key|token|password|secret)=)[^&\s]+", r"\1[REDACTED]", value
        )[:10000]
    return value


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def validate_url(url, domains, resolve=True):
    u = urlsplit(url)
    if u.scheme not in ("http", "https") or not u.hostname or u.username or u.password:
        raise ValueError("仅允许无凭证的 HTTP(S) URL")
    host = u.hostname.lower().rstrip(".")
    if host not in domains:
        raise ValueError("目标域名未在白名单内")
    demo = urlsplit(settings.DEMO_ORIGIN)
    if settings.ALLOW_DEMO and (u.scheme, host, u.port) == (
        demo.scheme,
        demo.hostname,
        demo.port,
    ):
        return url
    if u.port not in (None, 80, 443):
        raise ValueError("仅允许标准 HTTP(S) 端口")
    if host in ("localhost", "metadata.google.internal") or host.endswith(
        (".localhost", ".local", ".internal")
    ):
        raise ValueError("禁止访问内部地址")
    if resolve:
        ips = {
            a[4][0]
            for a in socket.getaddrinfo(host, u.port or 443, type=socket.SOCK_STREAM)
        }
        if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
            raise ValueError("禁止访问非公网地址")
    else:
        try:
            if not ipaddress.ip_address(host).is_global:
                raise ValueError("禁止访问非公网地址")
        except ValueError as e:
            if "禁止" in str(e):
                raise
    return url


def safe_url(url):
    u = urlsplit(url)
    return urlunsplit((u.scheme, u.netloc, u.path, "", ""))
