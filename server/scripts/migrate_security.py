"""Prepare and apply the security schema/data migration without printing secrets.

Run --schema-sql for the cloud administrator. --apply must only run after
maintenance/read-only mode, a verified backup, and deploying the new reader.
Existing plaintext is accepted only during this migration period.
"""
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import inspect, select, update
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.dialects import postgresql
from app.core.database import Base, SessionLocal, engine
from app.core.encryption import EncryptedBytes, EncryptedJSON, EncryptedText, PREFIX, cipher, decrypt, encrypt
from app.core.config import settings
from app.models import AuthSession, AuthThrottle, SensitiveGrant, Template, LibraryAdmin, User, MfaCredential, MfaChallenge, MfaRecovery

NEW = (AuthSession.__table__, AuthThrottle.__table__, SensitiveGrant.__table__, LibraryAdmin.__table__,
       MfaCredential.__table__, MfaChallenge.__table__, MfaRecovery.__table__)


def schema_sql():
    assert settings.DATABASE_SCHEMA == 'capstone', 'Use DATABASE_SCHEMA=capstone for cloud SQL.'
    lines=[]
    for table in NEW:
        lines.append(str(CreateTable(table,if_not_exists=True).compile(dialect=postgresql.dialect()))+';')
        for index in table.indexes:
            lines.append(str(CreateIndex(index,if_not_exists=True).compile(dialect=postgresql.dialect()))+';')
        lines += [f'ALTER TABLE capstone.{table.name} ENABLE ROW LEVEL SECURITY;',
                  f'DROP POLICY IF EXISTS backend_access ON capstone.{table.name};',
                  f'CREATE POLICY backend_access ON capstone.{table.name} FOR ALL TO capstone_api USING (true) WITH CHECK (true);',
                  f'GRANT SELECT, INSERT, UPDATE, DELETE ON capstone.{table.name} TO capstone_api;']
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            if isinstance(column.type, EncryptedText):
                lines.append(f'ALTER TABLE capstone.{table.name} ALTER COLUMN {column.name} TYPE TEXT;')
    return '\n'.join(line.rstrip() for line in '\n'.join(lines).strip().splitlines())


def migrate_data(db, *, rotate_files=False):
    counts={}
    for table in Base.metadata.sorted_tables:
        columns=[col for col in table.columns if isinstance(col.type,(EncryptedText,EncryptedJSON,EncryptedBytes))]
        if not columns:continue
        keys=list(table.primary_key.columns)
        count=0
        # Existing app is small; stream rows to avoid loading all original files into memory.
        for row in db.execute(select(table).execution_options(yield_per=50)):
            record=row._mapping
            data={col.name:record[col.name] for col in columns}
            db.execute(update(table).where(*(col==record[col.name] for col in keys)).values(**data))
            count+=1
        counts[table.name]=count
    # Encrypt legacy local originals atomically, including existing HWPX sidecars.
    if not settings.CLOUD_MODE:
        from app.core.encryption import PREFIX
        for template in db.scalars(select(Template).where(Template.source_path.is_not(None))):
            source=template.source_path
            if source.startswith('dbfile://'):continue
            path=Path(source)
            for target in (path,path.with_suffix('.hwpx')) if template.source_type=='hwp' else (path,):
                if not target.is_file():continue
                data=target.read_bytes()
                if data.startswith(PREFIX):
                    decrypt(data)  # Check key availability; never silently preserve unreadable files.
                    if not rotate_files:
                        continue
                    data = decrypt(data)
                if rotate_files and not target.resolve().is_relative_to(settings.UPLOAD_DIR.resolve()):
                    raise RuntimeError('Original file is outside the configured upload directory; rotation stopped.')
                temporary=target.with_name(target.name+'.encrypting')
                temporary.write_bytes(encrypt(data))
                if decrypt(temporary.read_bytes()) != data:
                    raise RuntimeError('Encrypted original verification failed; original retained.')
                os.replace(temporary,target)
    return counts


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--schema-sql',action='store_true')
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--backup-confirmed',action='store_true')
    parser.add_argument('--preserve-existing-admins',action='store_true',help='Snapshot existing reviewed admin email assignments to user IDs once, during cutover.')
    args=parser.parse_args()
    if args.schema_sql:
        print(schema_sql());return
    if not args.apply:
        print('Plan: add security/MFA tables, preserve existing accounts, encrypt supported fields and local originals. Use --schema-sql for PostgreSQL.');return
    if not args.backup_confirmed:
        raise SystemExit('A verified backup and write pause are required before applying.')
    cipher()
    if not settings.CLOUD_MODE:
        Base.metadata.create_all(engine)
        from main import ensure_company_columns, ensure_contract_columns
        ensure_company_columns()
        ensure_contract_columns()
    elif not all(inspect(engine).has_table(table.name,schema=settings.DATABASE_SCHEMA) for table in NEW):
        raise SystemExit('Apply the security schema SQL with the cloud administrator first.')
    with SessionLocal() as db:
        if args.preserve_existing_admins:
            for user in db.scalars(select(User)):
                if user.email.lower() in settings.LIBRARY_ADMIN_EMAILS and not db.get(LibraryAdmin,user.id):
                    db.add(LibraryAdmin(user_id=user.id))
        counts=migrate_data(db)
        db.commit()
    print({'migrated_rows':counts,'credentials_printed':False})


if __name__=='__main__':main()
