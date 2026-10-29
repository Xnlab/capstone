"""Authenticated encryption with keys separated from the database.

Readers accept legacy rows only to allow an explicit, resumable migration.
New writes are always encrypted. Keep every active key until backups expire.
"""
import json
import os
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet, MultiFernet
from sqlalchemy import JSON, LargeBinary, Text
from sqlalchemy.types import TypeDecorator

PREFIX = b'CDOCENC1:'


@lru_cache(maxsize=1)
def cipher():
    from app.core.config import settings
    configured = os.getenv('DATA_ENCRYPTION_KEYS', '')
    keys = [key.strip().encode() for key in configured.split(',') if key.strip()]
    if not keys:
        if settings.CLOUD_MODE:
            raise RuntimeError('DATA_ENCRYPTION_KEYS must be configured separately from the database.')
        path = settings.STORAGE_DIR / '.data-encryption.key'
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, 'wb') as target:
                target.write(Fernet.generate_key())
        keys = [path.read_bytes().strip()]
    return MultiFernet([Fernet(key) for key in keys])


def encrypt(data: bytes) -> bytes:
    return PREFIX + cipher().encrypt(data)


def decrypt(data: bytes) -> bytes:
    return cipher().decrypt(data[len(PREFIX):]) if data.startswith(PREFIX) else data


class EncryptedText(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return encrypt(value.encode()).decode() if value else value

    def process_result_value(self, value, dialect):
        return decrypt(value.encode()).decode() if value else value


class EncryptedJSON(TypeDecorator):
    impl = JSON
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return {'_cdoc_encrypted_v1': encrypt(json.dumps(value, ensure_ascii=False).encode()).decode()} if value is not None else None

    def process_result_value(self, value, dialect):
        if isinstance(value, dict) and set(value) == {'_cdoc_encrypted_v1'}:
            return json.loads(decrypt(value['_cdoc_encrypted_v1'].encode()))
        return value


class EncryptedBytes(TypeDecorator):
    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return encrypt(bytes(value)) if value is not None else None

    def process_result_value(self, value, dialect):
        return decrypt(bytes(value)) if value is not None else None
