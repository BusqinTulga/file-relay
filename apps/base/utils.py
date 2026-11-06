"""Bounded administrator login limiter."""
from apps.base.dependencies import IPRateLimit
from core.settings import settings

ip_limit = {"login": IPRateLimit(count=settings.login_count, minutes=settings.login_minute)}
