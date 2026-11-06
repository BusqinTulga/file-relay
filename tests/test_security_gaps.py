import asyncio
import unittest
from pathlib import Path
from fastapi import HTTPException
from apps.admin import views as admin_views
from apps.admin.schemas import LoginData
from apps.base.dependencies import IPRateLimit
from apps.base.utils import ip_limit
from core.settings import settings
from core.utils import hash_password
from tests.helpers import SettingsOverrideMixin

class LoginRateLimitTests(SettingsOverrideMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        settings.admin_token = hash_password("correct-password-123")
        settings.jwt_secret = "j" * 48
        settings.login_count = 3
        settings.login_minute = 15
        self._original_login_limiter = ip_limit["login"]
        ip_limit["login"] = IPRateLimit(count=3, minutes=15)

    def tearDown(self):
        ip_limit["login"] = self._original_login_limiter
        super().tearDown()

    def test_failed_logins_are_rate_limited(self):
        async def attempt(password: str):
            return await admin_views.login(
                data=LoginData(password=password), ip="203.0.113.10"
            )

        for _ in range(3):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(attempt("wrong-password"))
            self.assertEqual(ctx.exception.status_code, 401)

        self.assertFalse(ip_limit["login"].check_ip("203.0.113.10"))

    def test_successful_login_does_not_consume_failure_quota(self):
        result = asyncio.run(
            admin_views.login(
                data=LoginData(password="correct-password-123"), ip="198.51.100.8"
            )
        )
        self.assertIn("token", result.detail)
        self.assertTrue(ip_limit["login"].check_ip("198.51.100.8"))


class DockerRuntimeUserTests(unittest.TestCase):
    def test_dockerfile_defaults_to_root_for_volume_compatibility(self):
        # 默认 root：兼容已有 data 卷权限；如需非 root 可由编排层自行指定 user
        text = Path("Dockerfile").read_text()
        self.assertNotIn("USER appuser", text)
        compose = Path("docker-compose.yml").read_text()
        self.assertNotIn('user: "1000:1000"', compose)


if __name__ == "__main__":
    unittest.main()
