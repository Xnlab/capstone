"""Signing-date persistence, legacy database upgrade, and document autofill."""
import unittest
from datetime import date
from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models import User, Template, Document, Contract
from app.schemas import ContractIn
from app.routers.contracts import create_contract, update_contract, get_contract, list_documents
from app.services.documents import auto_values
from app.professional_templates import BUILTIN_TEMPLATES
from main import ensure_contract_columns


class ContractDateTests(unittest.TestCase):
    def test_contract_save_refreshes_missing_fields_and_preserves_manual_edits(self):
        engine = create_engine('sqlite://')
        Base.metadata.create_all(engine)
        try:
            with Session(engine) as db:
                user = User(email='sync@example.com', password_hash='test-only', name='테스트')
                db.add(user)
                db.commit()
                initial = dict(contract_title='기존 계약', amount=11000000, contract_date=None)
                created = create_contract(ContractIn(**initial), user, db)
                contract = db.get(Contract, created['id'])
                definition = next(t['definition'] for t in BUILTIN_TEMPLATES if t['key'] == 'completion')
                template = Template(kind='builtin', name='완료계', definition=definition)
                db.add(template)
                db.flush()
                values = auto_values(db, user.id, template, None, contract)
                values['completion_details'] = '직접 작성한 수행 결과'
                values['detail_items'] = '사용자 작성 항목|1|10000000|'
                doc = Document(contract_id=contract.id, template_id=template.id, title='완료계', values=values, status='reviewed')
                db.add(doc)
                db.commit()
                self.assertIn('contract_date', list_documents(contract.id, user, db)[0]['missing'])
                edited = dict(initial, contract_title='수정 계약', amount=22000000, contract_date='2026-10-14')
                update_contract(contract.id, ContractIn(**edited), user, db)
                db.expire_all()
                output = list_documents(contract.id, user, db)[0]
                self.assertNotIn('contract_date', output['missing'])
                self.assertEqual(output['values']['contract_date'], '2026. 10. 14.')
                self.assertEqual(output['values']['contract_title'], '수정 계약')
                self.assertEqual(output['values']['amount'], '22,000,000원')
                self.assertEqual(output['values']['completion_details'], '직접 작성한 수행 결과')
                self.assertEqual(output['values']['detail_items'], '사용자 작성 항목|1|10000000|')
                self.assertEqual(output['status'], 'draft')
                # Saving unchanged contract info also fills a legacy document's blank date.
                doc = db.get(Document, doc.id)
                doc.values = {**doc.values, 'contract_date': ''}
                db.commit()
                update_contract(contract.id, ContractIn(**edited), user, db)
                self.assertNotIn('contract_date', list_documents(contract.id, user, db)[0]['missing'])
        finally:
            engine.dispose()

    def test_date_survives_save_edit_and_autofills_document(self):
        engine = create_engine('sqlite://')
        Base.metadata.create_all(engine)
        try:
            with Session(engine) as db:
                user = User(email='date@example.com', password_hash='test-only', name='테스트')
                db.add(user)
                db.commit()
                data = dict(contract_title='계약일자 확인', contract_date='2026-10-14', start_date='2026-10-15')
                created = create_contract(ContractIn(**data), user, db)
                self.assertEqual(created['contract_date'], date(2026, 10, 14))
                db.expire_all()
                loaded = get_contract(created['id'], user, db)
                self.assertEqual(loaded['contract_date'], date(2026, 10, 14))
                data['contract_date'] = '2026-10-13'
                updated = update_contract(created['id'], ContractIn(**data), user, db)
                from app.models import Contract
                contract = db.get(Contract, updated['id'])
                definition = next(t['definition'] for t in BUILTIN_TEMPLATES if t['key'] == 'completion')
                template = Template(kind='builtin', definition=definition)
                values = auto_values(db, user.id, template, None, contract)
                self.assertEqual(values['contract_date'], '2026. 10. 13.')
                data['contract_date'] = None
                cleared = update_contract(created['id'], ContractIn(**data), user, db)
                self.assertIsNone(cleared['contract_date'])
        finally:
            engine.dispose()

    def test_legacy_upgrade_preserves_existing_rows_and_is_repeatable(self):
        engine = create_engine('sqlite://')
        try:
            with engine.begin() as connection:
                connection.execute(text('CREATE TABLE contracts (id INTEGER PRIMARY KEY, contract_title VARCHAR(200))'))
                connection.execute(text("INSERT INTO contracts VALUES (1, 'existing')"))
            with patch('main.engine', engine):
                ensure_contract_columns()
                ensure_contract_columns()
            with engine.connect() as connection:
                row = connection.execute(text('SELECT contract_title, contract_date FROM contracts')).one()
                self.assertEqual(tuple(row), ('existing', None))
        finally:
            engine.dispose()
