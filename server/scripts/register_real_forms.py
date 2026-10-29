"""Register reviewed official originals and verify the real API against a separate sample user.

Uses local storage/app.db. Does not change the real user's company or contracts.
Run prepare_real_forms.py and visually inspect its PNGs first.
"""
import hashlib
import io
import json
import secrets
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pymupdf
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import create_access_token, hash_password, csrf_token, SESSION_COOKIE
from app.models import Company, Contract, Document, Template, User
from app.services.library import is_admin
from main import app
from real_form_manifest import FORMS

ROOT = Path(__file__).resolve().parents[2] / "work" / "real-forms"


def checked(response):
    if response.status_code >= 400:
        raise RuntimeError(f"{response.status_code}: {response.text[:500]}")
    return response.json()


def main():
    verification = {row["key"]: row for row in json.loads((ROOT / "verification.json").read_text(encoding="utf-8"))}
    with SessionLocal() as db:
        admin = next((u for u in db.scalars(select(User)) if is_admin(u)), None)
        if not admin:
            raise RuntimeError("승인된 library_admins 사용자 ID가 필요합니다.")
        tester = db.scalar(select(User).where(User.email == "real-form-verification@example.invalid"))
        if not tester:
            tester = User(email="real-form-verification@example.invalid", name="자동작성 검증용", password_hash=hash_password(secrets.token_urlsafe(24)))
            db.add(tester); db.flush(); db.add(Company(user_id=tester.id)); db.commit()
        admin_token = create_access_token(admin.id, db)
        tester_token = create_access_token(tester.id, db)
        db.commit()
        admin_headers = {"Cookie": f"{SESSION_COOKIE}={admin_token}", "X-CSRF-Token": csrf_token(admin_token)}
        tester_headers = {"Cookie": f"{SESSION_COOKIE}={tester_token}", "X-CSRF-Token": csrf_token(tester_token)}
        tester_id = tester.id

    report = []
    with TestClient(app) as client:
        checked(client.put("/api/v1/company", headers=tester_headers, json={"company_name": "주식회사 자동작성검증", "representative": "김검증", "address": "대전광역시 유성구 대학로 99", "business_number": "123-45-67890", "phone": "010-0000-0000", "email": "verify@example.invalid"}))
        for spec in FORMS:
            original = ROOT / (spec["file"] + ".pdf")
            assert hashlib.sha256(original.read_bytes()).hexdigest() == verification[spec["key"]]["original_sha256"]
            with SessionLocal() as db:
                existing = db.scalar(select(Template).where(Template.key == spec["key"]))
                template_id = existing.id if existing else None
            if template_id is None:
                uploaded = checked(client.post("/api/v1/templates/upload?organization_library=true", headers=admin_headers, files={"file": (original.name, original.read_bytes(), "application/pdf")}))
                template_id = uploaded["template"]["id"]
                checked(client.put(f"/api/v1/templates/{template_id}/metadata", headers=admin_headers, json={
                    "scope": "organization", "organization": spec["organization"], "document_type": spec["document_type"],
                    "source_url": spec["source_url"], "version": "2025 공고 원본 · 입력 위치 검증", "project_code": spec["project_code"],
                    "usage_terms": "나라장터 공개 공고의 해당 사업 제출용 양식. 2025년 공고에 한정하며 타 사업 적용·재배포 권한은 별도 확인 필요. 인감·서명 자동 생성 안 함.",
                    "review_note": f"원본 {spec['page']+1}쪽에서 추출. {len(spec['fields'])}개 위치 대조, 샘플 입력 및 고정 문구·표·페이지 시각 검토. 제출 전 공고의 최신 적용 여부를 확인해야 함."
                }))
                checked(client.put(f"/api/v1/templates/{template_id}/mapping", headers=admin_headers, json={"name": spec["name"], "category": "보안·서약" if spec["document_type"] != "사용인감계" else "인감·확인", "fields": spec["fields"]}))
                checked(client.post(f"/api/v1/templates/{template_id}/publish", headers=admin_headers, json={"mapping_checked": True, "output_checked": True, "rights_checked": True}))
                with SessionLocal() as db:
                    db.get(Template, template_id).key = spec["key"]; db.commit()
            title = "[자동작성 검증] " + spec["project_code"]
            with SessionLocal() as db:
                existing = db.scalar(select(Contract).where(Contract.user_id == tester_id, Contract.contract_title == title))
                contract_id = existing.id if existing else None
            if contract_id is None:
                contract_id = checked(client.post("/api/v1/contracts", headers=tester_headers, json={"contract_title": title, "client_name": spec["organization"], "amount": 11000000, "description": "외부 제출하지 않는 자동작성 검증용", "start_date": "2026-10-22", "end_date": "2026-11-22"}))["id"]
            with SessionLocal() as db:
                existing = db.scalar(select(Document).where(Document.contract_id == contract_id, Document.template_id == template_id))
                document_id = existing.id if existing else None
            if document_id is None:
                assert client.post(f"/api/v1/contracts/{contract_id}/documents", headers=tester_headers, json={"template_id": template_id, "project_code": "WRONG"}).status_code == 400
                document_id = checked(client.post(f"/api/v1/contracts/{contract_id}/documents", headers=tester_headers, json={"template_id": template_id, "project_code": spec["project_code"]}))["id"]
            doc = checked(client.get(f"/api/v1/documents/{document_id}", headers=tester_headers))
            assert not doc["missing"] and doc["output_format"] == "pdf"
            # Edit and then reapply using the same paths as the browser editor.
            edited = checked(client.put(f"/api/v1/documents/{document_id}", headers=tester_headers, json={"values": {"representative": "이수정"}}))
            assert edited["values"]["representative"] == "이수정"
            doc = checked(client.post(f"/api/v1/documents/{document_id}/reapply", headers=tester_headers))
            assert doc["values"]["representative"] == "김검증"
            response = client.get(f"/api/v1/documents/{document_id}/download?format=native", headers=tester_headers)
            assert response.status_code == 200 and response.headers["content-type"] == "application/pdf"
            assert client.get(f"/api/v1/documents/{document_id}/download?format=docx", headers=tester_headers).status_code == 400
            output = ROOT / (spec["file"] + "-api.pdf"); output.write_bytes(response.content)
            with pymupdf.open(stream=response.content, filetype="pdf") as pdf:
                for field in spec["fields"]:
                    text = pdf[0].get_textbox(pymupdf.Rect(field["location"]["rect"]))
                    assert doc["values"][field["field_key"]].replace(" ", "") in text.replace(" ", "")
                pdf[0].get_pixmap(matrix=pymupdf.Matrix(1.3, 1.3)).save(ROOT / (spec["file"] + "-api.png"))
            preview = checked(client.get(f"/api/v1/documents/{document_id}/preview", headers=tester_headers))
            assert "data:image/png;base64," in preview["html"]
            validation = checked(client.post(f"/api/v1/contracts/{contract_id}/validate", headers=tester_headers))
            assert validation["summary"]["passed"]
            exported = client.get(f"/api/v1/contracts/{contract_id}/export?format=both", headers=tester_headers)
            assert exported.status_code == 200
            with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
                names = archive.namelist(); assert len(names) == len(set(names))
                assert all(name.endswith(".pdf") for name in names)
            results = checked(client.get("/api/v1/templates/search", headers=tester_headers, params={"q": spec["document_type"], "contract_id": contract_id, "project_code": spec["project_code"]}))["results"]
            assert any(r["template"]["id"] == template_id for r in results)
            assert results[0]["template"]["library"]["scope"] == "organization"
            assert client.get(f"/api/v1/documents/{document_id}", headers=admin_headers).status_code == 404
            report.append({**verification[spec["key"]], "template_id": template_id, "sample_document_id": document_id, "sample_user_only": True, "api_create_edit_reapply_preview_pdf_zip_validate": "passed", "project_guard": "passed", "sample_file": str(output)})
    (ROOT / "api-verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
