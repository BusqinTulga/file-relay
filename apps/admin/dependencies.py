"""Administrator authentication and service dependencies."""
from fastapi import Header, Request
from apps.admin.config_service import ConfigService
from apps.admin.services import FileService
from apps.base.auth import _extract_bearer_token, _require_admin_payload


def get_admin_session(authorization: str = Header(default=None)) -> dict:
    payload = _require_admin_payload(authorization)
    return {"id": "admin", "username": "admin", "token": _extract_bearer_token(authorization),
            "token_type": "Bearer", "expires_at": payload.get("exp")}


async def admin_required(request: Request, authorization: str = Header(default=None)):
    if (request.method, request.url.path) != ("POST", "/admin/login"):
        return _require_admin_payload(authorization)


def get_file_service():
    return FileService()


def get_config_service():
    return ConfigService()
