"""Authenticated encryption with keys separated from the database.

Readers accept legacy rows only to allow an explicit, resumable migration.
New writes are always encrypted. Keep every active key until backups expire.
"""
import json
import os
import hashlib
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet, MultiFernet
from sqlalchemy import JSON, LargeBinary, Text
from sqlalchemy.types import TypeDecorator

PREFIX = b'CDOCENC1:'


def key_material():
    from app.core.config import settings
    configured = os.getenv('DATA_ENCRYPTION_KEYS', '')
    key_file = os.getenv('DATA_ENCRYPTION_KEY_FILE', '')
    if configured and key_file:
        raise RuntimeError('Configure exactly one encryption key source.')
    if key_file:
        source = Path(key_file)
        if not source.is_absolute() or source.is_symlink() or not source.is_file():
            raise RuntimeError('Encryption key file must be an existing absolute regular file, not a symlink.')
        if os.name != 'nt' and source.stat().st_mode & 0o077:
            raise RuntimeError('Encryption key file must not be accessible to group/other users.')
        if source.stat().st_size > 8192:
            raise RuntimeError('Encryption key file is too large.')
        configured = source.read_text(encoding='ascii').strip()
        if not configured:
            raise RuntimeError('Encryption key file is empty.')
    keys = [key.strip().encode() for key in configured.split(',') if key.strip()]
    if configured and not keys:
        raise RuntimeError('Configured encryption key source contains no keys.')
    if not keys:
        if settings.CLOUD_MODE:
            raise RuntimeError('DATA_ENCRYPTION_KEYS must be configured separately from the database.')
        path = settings.STORAGE_DIR / '.data-encryption.key'
        if path.is_symlink():
            raise RuntimeError('Local encryption key must not be a symlink.')
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, 'wb') as target:
                target.write(Fernet.generate_key())
        keys = [path.read_bytes().strip()]
    try:
        for key in keys:
            Fernet(key)
    except (ValueError, TypeError):
        raise RuntimeError('Invalid encryption key configuration.') from None
    if len(set(keys)) != len(keys):
        raise RuntimeError('Duplicate encryption keys are not allowed.')
    return keys


def key_status():
    keys = key_material()
    return {'source': 'mounted_file' if os.getenv('DATA_ENCRYPTION_KEY_FILE') else 'environment' if os.getenv('DATA_ENCRYPTION_KEYS') else 'local_file',
            'primary_id': hashlib.sha256(keys[0]).hexdigest()[:16],
            'retained_ids': [hashlib.sha256(key).hexdigest()[:16] for key in keys[1:]],
            'key_values_printed': False}


@lru_cache(maxsize=1)
def cipher():
    return MultiFernet([Fernet(key) for key in key_material()])


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
