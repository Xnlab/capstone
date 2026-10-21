"use client";

import type { LibraryMetadata } from "@/lib/types";
import { Field, Input } from "@/components/ui";

export default function LibraryMetadataEditor({ value, onChange, admin }: {
  value: LibraryMetadata; onChange: (value: LibraryMetadata) => void; admin: boolean;
}) {
  const set = (key: keyof LibraryMetadata, text: string) => onChange({ ...value, [key]: text });
  return <div className="grid gap-4 sm:grid-cols-2">
    {admin && <Field label="보관 구분"><select className="h-10 w-full rounded-lg border border-line px-3" value={value.scope} onChange={e => onChange({ ...value, scope: e.target.value as "private" | "organization" })}>
      <option value="private">내 업로드 양식</option><option value="organization">기관·기업 지정 양식 (검토 후 공개)</option>
    </select></Field>}
    <Field label="발주처·기관·기업명"><Input value={value.organization ?? ""} onChange={e => set("organization", e.target.value)} placeholder="예: 부산광역시" /></Field>
    <Field label="서류 종류"><Input value={value.document_type ?? ""} onChange={e => set("document_type", e.target.value)} placeholder="예: 착수계" /></Field>
    <Field label="출처 링크"><Input type="url" value={value.source_url ?? ""} onChange={e => set("source_url", e.target.value)} placeholder="https://…" /></Field>
    <Field label="게시일"><Input type="date" value={value.source_date ?? ""} onChange={e => set("source_date", e.target.value)} /></Field>
    <Field label="버전"><Input value={value.version ?? ""} onChange={e => set("version", e.target.value)} placeholder="예: 2026년 1월 게시본" /></Field>
    <Field label="공고·사업번호 (해당 시)"><Input value={value.project_code ?? ""} onChange={e => set("project_code", e.target.value)} /></Field>
    <Field label="이용 조건"><Input value={value.usage_terms ?? ""} onChange={e => set("usage_terms", e.target.value)} placeholder="출처의 이용 조건 및 확인 내용" /></Field>
    {value.scope === "organization" && <Field label="검토 메모"><Input value={value.review_note ?? ""} onChange={e => set("review_note", e.target.value)} placeholder="매핑·고정 문구·출력 확인 내용" /></Field>}
  </div>;
}

export function metadataPayload(value: LibraryMetadata) {
  return { ...value, source_url: value.source_url || null, source_date: value.source_date || null };
}
