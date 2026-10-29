"""Safe status/rotation/verification. Never prints key or document values.

Provision new keys through a secrets manager. Configure newest-first plus all
retained old keys, restart all readers, pause writes and verify backups first.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cryptography.fernet import Fernet
from sqlalchemy import select, String, LargeBinary, cast
from app.core.config import settings
from app.core.database import Base, SessionLocal
from app.core.encryption import EncryptedBytes, EncryptedJSON, EncryptedText, PREFIX, key_material, key_status
from app.models import Template
from scripts.migrate_security import migrate_data


def verify_primary(db):
    """Raw storage reads bypass TypeDecorators to prove ciphertext uses primary key."""
    primary = Fernet(key_material()[0])
    count = 0
    for table in Base.metadata.sorted_tables:
        for col in table.columns:
            if not isinstance(col.type, (EncryptedText, EncryptedJSON, EncryptedBytes)):
                continue
            raw_type = LargeBinary if isinstance(col.type, EncryptedBytes) else String
            for value in db.scalars(select(cast(col, raw_type)).execution_options(yield_per=50)):
                if value is None or value == '':
                    continue
                if isinstance(col.type, EncryptedJSON):
                    value = json.loads(value)
                    if not isinstance(value, dict) or set(value) != {'_cdoc_encrypted_v1'}:
                        raise RuntimeError('Unencrypted JSON found; migration required.')
                    value = value['_cdoc_encrypted_v1']
                data = value.encode() if isinstance(value, str) else bytes(value)
                if not data.startswith(PREFIX):
                    raise RuntimeError('Unencrypted data found; migration required.')
                primary.decrypt(data[len(PREFIX):])
                count += 1
    files = 0
    if not settings.CLOUD_MODE:
        for template in db.scalars(select(Template).where(Template.source_path.is_not(None))):
            if template.source_path.startswith('dbfile://'):
                continue
            path = Path(template.source_path)
            for target in (path, path.with_suffix('.hwpx')) if template.source_type == 'hwp' else (path,):
                if not target.is_file():
                    raise RuntimeError('Referenced original file is missing; verification stopped.')
                data = target.read_bytes()
                if not data.startswith(PREFIX):
                    raise RuntimeError('Unencrypted original found; migration required.')
                primary.decrypt(data[len(PREFIX):])
                files += 1
    return {'verified_encrypted_values': count, 'verified_originals': files, 'backups_checked': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['status', 'rotate', 'verify'])
    parser.add_argument('--backup-confirmed', action='store_true')
    parser.add_argument('--writes-paused', action='store_true')
    args = parser.parse_args()
    try:
        if args.action == 'status':
            print(key_status())
            return
        if args.action == 'rotate' and not (args.backup_confirmed and args.writes_paused):
            raise RuntimeError('Rotation requires a verified backup and paused writes on every instance.')
        with SessionLocal() as db:
            if args.action == 'rotate':
                migrate_data(db, rotate_files=True)
                db.commit()
            result = verify_primary(db)
        print({**key_status(), **result})
    except Exception as exc:
        # Provider exceptions can contain URLs/parameters. Do not echo exception data.
        raise SystemExit(f'Key operation failed ({type(exc).__name__}); retain all old keys and inspect configuration/backup safely.') from None


if __name__ == '__main__':
    main()
