import asyncio
import hashlib
import os
import re
import secrets
import uuid
from collections import OrderedDict
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from tortoise.transactions import in_transaction

from apps.base.models import FileCodes, PairingRequest, RelayDevice, RelayGroup, RelaySession, RelayUpload
from apps.relay import config

router = APIRouter(prefix="/api/relay")
# Single worker is intentional. Serialize authorization changes, quota reservations,
# publication and deletion admission; no filesystem/network IO inside transactions.
state_lock = asyncio.Lock()
SESSION_COOKIE = "relay_device"
PENDING_COOKIE = "relay_pending"
CSRF_COOKIE = "relay_csrf"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def cookie(response: Response, request: Request, name: str, value: str, max_age=config.COOKIE_AGE):
    response.set_cookie(name, value, httponly=True, samesite="strict", max_age=max_age,
                        secure=request.url.scheme == "https" or os.getenv("APP_ENV") in {"production", "prod"},
                        path="/")


async def optional_session(request: Request):
    token = request.cookies.get(SESSION_COOKIE, "")
    return await RelaySession.filter(token_hash=digest(token), valid=True).first() if token else None


async def device_session(request: Request):
    session = await optional_session(request)
    if not session:
        raise HTTPException(401, "设备凭证已失效，请重新输入口令")
    expected = request.headers.get("x-relay-session")
    if expected and expected != session.token_hash:
        raise HTTPException(409, "配对已在其他标签页改变，请刷新")
    device = await RelayDevice.get_or_none(id=session.device_id)
    if not device:
        raise HTTPException(401, "设备不存在")
    return session, device


async def csrf(request: Request):
    origin = request.headers.get("origin", "")
    expected = urlsplit(str(request.base_url))
    actual = urlsplit(origin)
    if (not origin or actual.scheme != expected.scheme or actual.netloc != expected.netloc
            or actual.path not in {"", "/"} or request.headers.get("sec-fetch-site") == "cross-site"):
        raise HTTPException(403, "请通过同源页面操作")
    session = await optional_session(request)
    value = session.csrf if session else request.cookies.get(CSRF_COOKIE, "")
    if not value or not secrets.compare_digest(value, request.headers.get("x-relay-csrf", "")):
        raise HTTPException(403, "CSRF 校验失败，请刷新页面")


_pair_limits: OrderedDict[str | None, list[float]] = OrderedDict()


def rate_limit(request):
    stamp = config.now()
    key = request.client.host if request.client else "unknown"
    # Bounded memory; a global bucket also bounds rotating-IP attempts.
    updates: dict[str | None, list[float]] = {}
    for bucket, limit in ((None, 200), (key, 10)):
        values = [t for t in _pair_limits.get(bucket, []) if t > stamp - 60]
        if len(values) >= limit:
            raise HTTPException(429, "配对操作过于频繁，请稍后重试", headers={"Retry-After": "60"})
        updates[bucket] = [*values, stamp]
    for bucket, values in updates.items():
        _pair_limits[bucket] = values
        _pair_limits.move_to_end(bucket)
    while len(_pair_limits) > 4096:
        _pair_limits.popitem(last=False)


class PairInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    passcode: str = Field(pattern=r"^[0-9]{1,4}$")


async def session_view(session, device):
    group = await RelayGroup.get(id=device.group_id)
    return {"paired": True, "passcode": group.passcode, "device_id": device.id,
            "session_id": session.token_hash, "csrf": session.csrf}


@router.get("/session")
async def get_session(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    async with state_lock:
        session = await optional_session(request)
        if session:
            device = await RelayDevice.get(id=session.device_id)
            result = await session_view(session, device)
        else:
            token = request.cookies.get(CSRF_COOKIE)
            if not token:
                token = secrets.token_urlsafe(32)
                cookie(response, request, CSRF_COOKIE, token)
            result = {"paired": False, "csrf": token}
        pending_token = request.cookies.get(PENDING_COOKIE)
        if pending_token:
            pending = await PairingRequest.get_or_none(
                token_hash=digest(pending_token), original_session=session.token_hash if session else None,
                status__in=["pending", "approved"], expires__gt=config.now())
            if pending:
                result["pending"] = {"request_id": pending.id, "status": pending.status, "expires": pending.expires}
        return result


async def join(group_id, original, response, request):
    """Called under state_lock + transaction, after target permission is established."""
    if original:
        current = await RelaySession.get_or_none(token_hash=original.token_hash, valid=True)
        if not current:
            raise HTTPException(409, "原设备状态已改变，请重新申请")
        device = await RelayDevice.get(id=current.device_id)
        await FileCodes.filter(uploader_device_id=device.id, delete_state="active",
                               relay_expires__gt=config.now()).update(relay_group_id=group_id)
        # A late completion cannot publish an old upload into either group.
        await RelayUpload.filter(device_id=device.id, state__in=["uploading", "merging"]).update(
            state="cancelled", error="设备已重新配对")
        device.group_id = group_id
        await device.save()
        await RelaySession.filter(device_id=device.id).update(valid=False)
    else:
        device = await RelayDevice.create(id=str(uuid.uuid4()), group_id=group_id)
    token = secrets.token_urlsafe(48)
    session = await RelaySession.create(token_hash=digest(token), device_id=device.id,
                                        csrf=secrets.token_urlsafe(32))
    cookie(response, request, SESSION_COOKIE, token)
    response.delete_cookie(PENDING_COOKIE, path="/")
    return await session_view(session, device)


@router.post("/pair", dependencies=[Depends(csrf)])
async def pair(data: PairInput, request: Request, response: Response):
    if not re.fullmatch(r"[0-9]{1,4}", data.passcode):
        raise HTTPException(422, "口令必须是 1 至 4 位数字")
    rate_limit(request)
    async with state_lock, in_transaction():
        original = await optional_session(request)
        group, _ = await RelayGroup.get_or_create(passcode=data.passcode, defaults={"created": config.now()})
        # Supersede the previous pending request for this browser, without touching its files.
        old = request.cookies.get(PENDING_COOKIE)
        if old:
            await PairingRequest.filter(token_hash=digest(old), status__in=["pending", "approved"]).update(
                status="cancelled")
        if original:
            device = await RelayDevice.get(id=original.device_id)
            if device.group_id == group.id:
                response.delete_cookie(PENDING_COOKIE, path="/")
                return await session_view(original, device)
        if await RelayDevice.filter(group_id=group.id).count() < 2:
            return await join(group.id, original, response, request)
        token = secrets.token_urlsafe(48)
        pending = await PairingRequest.create(
            id=str(uuid.uuid4()), token_hash=digest(token), group_id=group.id,
            original_session=original.token_hash if original else None, expires=config.now() + config.PAIR_TTL)
        cookie(response, request, PENDING_COOKIE, token, config.PAIR_TTL)
        return {"paired": False, "status": "pending", "request_id": pending.id, "expires": pending.expires}


@router.post("/pairing/status", dependencies=[Depends(csrf)])
async def pairing_status(request: Request, response: Response):
    async with state_lock, in_transaction():
        pending = await PairingRequest.get_or_none(token_hash=digest(request.cookies.get(PENDING_COOKIE, "")))
        if not pending:
            return {"status": "expired"}
        if pending.status in {"pending", "approved"} and pending.expires <= config.now():
            pending.status = "expired"
            await pending.save()
        if pending.status == "approved":
            original = None
            if pending.original_session:
                original = await optional_session(request)
                if not original or original.token_hash != pending.original_session:
                    raise HTTPException(409, "原设备状态已改变，请重新申请")
            result = await join(pending.group_id, original, response, request)
            pending.status = "joined"
            await pending.save()
            return result
        return {"status": pending.status, "expires": pending.expires}


@router.get("/pairing/requests")
async def pairing_requests(auth=Depends(device_session)):
    _, device = auth
    return [{"id": item.id, "expires": item.expires} for item in await PairingRequest.filter(
        group_id=device.group_id, status="pending", expires__gt=config.now()).order_by("expires")]


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    approve: bool


@router.post("/pairing/requests/{request_id}", dependencies=[Depends(csrf)])
async def decide(request_id: str, data: Decision, auth=Depends(device_session)):
    session, device = auth
    async with state_lock, in_transaction():
        current = await RelayDevice.get(id=device.id)
        valid = await RelaySession.filter(token_hash=session.token_hash, valid=True).exists()
        pending = await PairingRequest.get_or_none(id=request_id, group_id=current.group_id)
        if not pending or not valid:
            raise HTTPException(404, "申请不存在")
        if pending.status == "pending":
            pending.status = "expired" if pending.expires <= config.now() else (
                "approved" if data.approve else "rejected")
            pending.confirmed_by = device.id
            pending.handled = config.now()
            await pending.save()
        return {"status": pending.status}
