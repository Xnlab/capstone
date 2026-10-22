# AI 기반 계약·행정서류 자동화 웹 서비스

스타트업·소규모 사업자를 위한 계약 행정업무 자동화 (CAPSTONE DESIGN · 구예찬 · 원정연 · 정한솔)

> 서류 요청 → AI 분석 → 자동 작성 → 검토·다운로드

## 실행

```bash
# 1) API 서버 (http://localhost:8000, 문서: /docs)
cd server
pip install -r requirements.txt
cp .env.example .env        # 필요 시 OPENAI_API_KEY, SMTP 설정
python -m uvicorn main:app --reload --port 8000

# 2) 웹 (http://localhost:3000)
cd web
npm install
npm run dev
```

- `OPENAI_API_KEY`가 비어 있으면 AI 기능은 **규칙 기반(동의어 사전 + 유사도)** 으로 동작합니다. 키 없이도 전체 흐름 시연 가능.
- `SMTP_HOST`가 비어 있으면 메일은 **MOCK**(실제 발송 없이 기록만)입니다.
- DB는 기본 SQLite(`server/storage/app.db`). `DATABASE_URL`로 PostgreSQL 전환 가능.
- 로컬 데모 계정: `demo@example.com` / `demo1234` (개발용, 최초 1회 회원가입 필요)
- 자체 양식 테스트용 샘플: `samples/B기업_용역착수신고서.docx`, `samples/C기업_비밀유지확약서.docx`

## 구현 범위 (2~3주차 설계 기준)

| 발표 내용 | 구현 |
|---|---|
| 2주차 · 양식 라이브러리 | 실무형 기본 양식 9종(견적서·산출내역서·착수계·과업수행계획서·완료계·보안서약서·사용인감계·선급금 지급 요청서·대금 지급 요청서), 카테고리·다른 이름 검색 |
| 2주차 · 요청 의도 분석 | "착수신고서 내라고 하네요" → 착수계 추천 (동의어/유사도, 키 있으면 LLM 보강) |
| 2주차 · 회사정보 반복 활용 | 회사 정보 1회 입력 → 모든 서류 자동 채움 |
| 2주차 · AI 자동 매핑·문장 생성 | 표준 필드 기반 자동 입력, 과업 개요 문장 AI 생성 |
| 2주차 · 누락·오류 검증 | 필수값 누락, 착수일>완료일, 공급가+부가세≠합계, 한글 금액 표기 오류, 사업자번호 형식 |
| 2주차 · 한글/Excel/PDF · 메일 | 견적서는 XLSX, 나머지 기본 양식은 HWPX, 검토·제출용 PDF, 계약 전체 ZIP, SMTP 메일 제출 |
| 3주차 · 기업 자체 양식 업로드 (CASE 2) | 한글(HWP·HWPX)/Word/PDF 업로드 → 표·문단에서 입력 칸 추출 → 항목명을 **의미로** 표준 필드에 매핑 → 사용자 확인·수정 → 원본 입력 칸에 값 채움(PDF는 재구성) |
| 3주차 · 서류 간 교차 검증 | 사용자가 서류별로 값을 고친 뒤 서류끼리 달라진 금액·기간·상호 등을 탐지 |
| 3주차 · 보안 5대 원칙 | ①최소 수집 ②마스킹(전화·이메일·계좌·주민번호) ③최소 전송(항목명+짧은 문맥) ④접근 통제(본인 데이터만) ⑤자동 삭제(보관기간 경과/요청 즉시) + 처리 이력 화면 |

**다음 단계**: 제출서류 안내문 AI 분석 → 체크리스트 자동 생성 (워크스페이스에 탭 자리만 마련됨)

## 구조

```
server/                         FastAPI
├── main.py                     앱 진입점, 기본 양식 시드, 만료 원본 삭제
└── app/
    ├── standard_fields.py      ★ 내부 표준 데이터(필드 사전·동의어·금액/날짜 파생값)
    ├── builtin_templates.py    기본 양식 정의 (제목·표·본문·첨부·서명란)
    ├── models.py               User, Company, Contract, Template, Document, AuditLog
    ├── routers/                auth, company, contracts, documents, templates
    └── services/
        ├── ai.py               LLM/규칙 기반 매핑·검색·문장 생성·문장 검토
        ├── masking.py          AI 전송 전 비식별화
        ├── form_parser.py      자체 양식(DOCX/PDF) 입력 칸 추출
        ├── renderer.py         내부 DOCX 미리보기와 PDF 파생 출력
        ├── professional_renderer.py  기본 양식 HWPX·견적서 XLSX 생성
        ├── validator.py        누락·형식·금액·서류 간 불일치 검증
        └── mailer.py           SMTP (MOCK 지원)

web/                            Next.js 16 (App Router) + Tailwind 4
└── src/
    ├── app/                    랜딩, 로그인/가입
    │   └── (app)/              dashboard, company, contracts/new,
    │                           contracts/[id] (워크스페이스),
    │                           contracts/[id]/documents/[docId] (편집·미리보기),
    │                           templates, templates/upload, templates/[id], security
    ├── components/             AppShell, ui, ContractForm, MappingEditor, workspace/*
    └── lib/                    api 클라이언트, 타입, 훅
```

## 설계 원칙

### 기관·기업 양식 라이브러리

- 라이브러리는 공통 양식 / 기관·기업 지정 양식 / 내 업로드로 구분합니다.
- `server/.env`의 `LIBRARY_ADMIN_EMAILS`에 관리자 이메일을 쉼표로 지정합니다. 기본값은 관리자 없음이며, 회원가입으로 권한을 얻을 수 없습니다.
- 관리자는 지정 양식 등록에서 DOCX 파일과 발주처·서류 종류·출처 URL·게시일·버전·공고번호·이용 조건을 입력하고, 매핑을 저장한 뒤 샘플 출력과 이용 조건을 검토하여 공개합니다.
- PDF는 항목 기반 DOCX로 재구성되므로 지정 양식으로 공개할 수 없습니다. DOCX·HWP·HWPX는 원본을 유지해 작성하며, XLS는 검토된 DOCX 편집용 파일로 준비합니다. 수집 출처 8곳은 링크 목록이며 등록된 양식이 아닙니다.

### 한글 양식 업로드

- HWPX는 원본 ZIP의 표·스타일·그림을 보존하고 매핑한 빈 셀, `항목명 : ____`, `{{contract_title}}` 표시자만 채워 HWPX로 내려받습니다. 원본 자체는 수정하지 않습니다.
- HWP는 설치된 한컴 한글로 편집용 HWPX를 생성합니다. 보관 원본은 HWP로 유지하고 작성 결과는 HWPX로 제공합니다.
- HWP 변환 및 HWP/HWPX의 PDF·페이지 미리보기에는 Windows의 한컴 한글 자동화 엔진이 필요합니다. HWPX 분석·작성·다운로드는 한글 설치 없이 동작합니다. 변환은 로컬에서 직렬 실행하며 외부 변환 서비스로 파일을 보내지 않습니다.
- 암호화·배포용 제한 문서는 변환에 실패할 수 있습니다. 자동화 파일 접근 확인창이 뜨는 환경에서는 한글 설치·운영 설정을 확인해야 합니다. 보안 설정을 자동으로 해제하지 않습니다.
- 한글 원본이 만료·삭제된 경우 임의로 다른 서식으로 재구성하지 않고 재업로드를 안내합니다.
- 공개 양식은 모든 회원이 조회할 수 있고 관리자만 수정할 수 있습니다. 이미 서류 작성에 사용한 지정 양식은 새 버전으로 등록해야 하며, 개인 양식은 관리자에게도 공개되지 않습니다.
- 계약의 발주처를 기준으로 사업 지정 → 발주처 지정 → 공통 양식을 추천합니다. 공고번호가 지정된 양식은 검색 화면에 같은 번호를 입력해야 추천·추가할 수 있습니다. 지정 양식이 없으면 기존 공통 양식으로 초안을 작성하며 타사 고유 문구를 자동 혼합하지 않습니다.
- 원본은 다운로드로 보존·확인할 수 있습니다. 기관·기업 지정 양식은 개인 업로드의 보관기간 삭제 대상에서 제외합니다.

검증: `cd server` 후 `../.venv/Scripts/python.exe -m unittest discover -s tests -v` (FastAPI TestClient 지원 환경).

- **표준 필드 사전이 중심**: 양식 분석·자동 작성·검증이 모두 같은 키(`amount`, `period` …)를 사용
- **LLM은 이해·분류·문장에만**: 금액·날짜 등 확정값은 코드로 채우고 코드로 검증
- **원본과 미리보기 분리**: 기본 양식의 편집 원본은 HWPX(견적서만 XLSX), 내부 DOCX는 HTML 미리보기와 PDF 파생에 사용
