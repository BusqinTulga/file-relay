"""Persistent FileRelay state. Historical schema lives only in migrations."""
from typing import Any
from tortoise import fields, models


class FileCodes(models.Model):
    id = fields.IntField(pk=True)
    prefix = fields.CharField(max_length=255, default="")
    suffix = fields.CharField(max_length=255, default="")
    size = fields.BigIntField(default=0)
    file_hash = fields.CharField(max_length=64, null=True)
    upload_id = fields.CharField(max_length=36, null=True)
    relay_group_id = fields.IntField(null=True, index=True)
    uploader_device_id = fields.CharField(max_length=36, null=True, index=True)
    published = fields.FloatField(null=True)
    relay_expires = fields.FloatField(null=True, index=True)
    first_sent = fields.FloatField(null=True)
    delete_state = fields.CharField(max_length=16, default="active")
    cleanup_error = fields.TextField(default="")


class KeyValue(models.Model):
    id = fields.IntField(pk=True)
    key = fields.CharField(max_length=255, unique=True, index=True)
    value: Any = fields.JSONField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)


class RelayGroup(models.Model):
    id = fields.IntField(pk=True)
    passcode = fields.CharField(max_length=4, unique=True)
    created = fields.FloatField()


class RelayDevice(models.Model):
    id = fields.CharField(max_length=36, pk=True)
    group_id = fields.IntField(index=True)


class RelaySession(models.Model):
    token_hash = fields.CharField(max_length=64, pk=True)
    device_id = fields.CharField(max_length=36, index=True)
    csrf = fields.CharField(max_length=64)
    valid = fields.BooleanField(default=True)


class PairingRequest(models.Model):
    id = fields.CharField(max_length=36, pk=True)
    token_hash = fields.CharField(max_length=64, unique=True)
    group_id = fields.IntField(index=True)
    original_session = fields.CharField(max_length=64, null=True)
    status = fields.CharField(max_length=16, default="pending")
    expires = fields.FloatField(index=True)
    confirmed_by = fields.CharField(max_length=36, null=True)
    handled = fields.FloatField(null=True)


class RelayUpload(models.Model):
    id = fields.CharField(max_length=36, pk=True)
    group_id = fields.IntField(index=True)
    device_id = fields.CharField(max_length=36, index=True)
    session_hash = fields.CharField(max_length=64)
    name = fields.CharField(max_length=255)
    size = fields.BigIntField()
    sha256 = fields.CharField(max_length=64)
    chunk_size = fields.IntField()
    state = fields.CharField(max_length=16, default="uploading", index=True)
    expires = fields.FloatField(index=True)
    file_id = fields.IntField(null=True)
    error = fields.TextField(default="")


class RelayChunk(models.Model):
    id = fields.IntField(pk=True)
    upload_id = fields.CharField(max_length=36)
    index = fields.IntField()
    size = fields.IntField()
    sha256 = fields.CharField(max_length=64)

    class Meta:
        unique_together = (("upload_id", "index"),)


class DownloadAttempt(models.Model):
    id = fields.CharField(max_length=36, pk=True)
    file_id = fields.IntField(index=True)
    group_id = fields.IntField()
    state = fields.CharField(max_length=16, default="active")
    lease_until = fields.FloatField(index=True)
    protect_until = fields.FloatField()
    completed = fields.FloatField(null=True)
