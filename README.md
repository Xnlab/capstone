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
| 2주차 · 양식 라이브러리 | 기본 양식 8종(착수계·완료계·견적서·산출내역서·보안서약서·사용인감계·과업수행계획서·확인서), 카테고리·다른 이름 검색 |
| 2주차 · 요청 의도 분석 | "착수신고서 내라고 하네요" → 착수계 추천 (동의어/유사도, 키 있으면 LLM 보강) |
| 2주차 · 회사정보 반복 활용 | 회사 정보 1회 입력 → 모든 서류 자동 채움 |
| 2주차 · AI 자동 매핑·문장 생성 | 표준 필드 기반 자동 입력, 과업 개요 문장 AI 생성 |
| 2주차 · 누락·오류 검증 | 필수값 누락, 착수일>완료일, 공급가+부가세≠합계, 한글 금액 표기 오류, 사업자번호 형식 |
| 2주차 · Word/PDF · 메일 | 서류별 DOCX/PDF, 계약 전체 ZIP, SMTP 메일 제출 |
| 3주차 · 기업 자체 양식 업로드 (CASE 2) | Word/PDF 업로드 → 표·문단에서 입력 칸 추출 → 항목명을 **의미로** 표준 필드에 매핑 → 사용자 확인·수정 → 원본 양식에 값 채움 |
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
        ├── renderer.py         DOCX 생성/채움 → PDF·HTML 미리보기
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

- **표준 필드 사전이 중심**: 양식 분석·자동 작성·검증이 모두 같은 키(`amount`, `period` …)를 사용
- **LLM은 이해·분류·문장에만**: 금액·날짜 등 확정값은 코드로 채우고 코드로 검증
- **모든 출력은 DOCX 한 경로**: DOCX → PDF / HTML 미리보기로 파생
