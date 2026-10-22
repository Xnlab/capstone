"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type DragEvent } from "react";
import { api } from "@/lib/api";
import { useQueryParam, useStandardFields } from "@/lib/hooks";
import type { LibraryMetadata, Template, TemplateField, UploadAnalysis } from "@/lib/types";
import LibraryMetadataEditor, { metadataPayload } from "@/components/LibraryMetadataEditor";
import MappingEditor from "@/components/MappingEditor";
import { Badge, Button, Card, CardHeader, ErrorText, Field, Input, PageHeader, Spinner } from "@/components/ui";

const STAGES = ["파일 업로드", "구조 분석", "의미 매핑", "확인·저장"];

export default function UploadTemplatePage() {
  const router = useRouter();
  const { fields: standard } = useStandardFields();
  const inputRef = useRef<HTMLInputElement>(null);
  const contractId = useQueryParam("contract");
  const libraryMode = useQueryParam("library");
  const organization = useQueryParam("organization");
  const source = useQueryParam("source");
  const [admin, setAdmin] = useState(false);
  const [error, setError] = useState("");
  const [meta, setMeta] = useState<LibraryMetadata>({ scope: "private" });
  useEffect(() => {
    api.get<{ is_admin: boolean }>("/templates/library-settings").then(s => {
      setAdmin(s.is_admin);
      setMeta({ scope: s.is_admin && libraryMode ? "organization" : "private", organization: organization || "", source_url: source || null });
    }).catch(e => setError(e.message));
  }, [libraryMode, organization, source]);
  const [drag, setDrag] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [template, setTemplate] = useState<Template | null>(null);
  const [analysis, setAnalysis] = useState<UploadAnalysis | null>(null);
  const [fields, setFields] = useState<TemplateField[]>([]);
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);

  const upload = async (file: File) => {
    setError("");
    setUploading(true);
    try {
      const r = await api.upload<{ template: Template; analysis: UploadAnalysis }>(`/templates/upload?organization_library=${admin && meta.scope === "organization"}`, file);
      setTemplate(r.template);
      setAnalysis(r.analysis);
      setFields(r.template.fields);
      setName(r.template.name);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUploading(false);
    }
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDrag(false);
    const f = e.dataTransfer.files[0];
    if (f) upload(f);
  };

  const save = async () => {
    if (!template) return;
    setSaving(true);
    setError("");
    try {
      await api.put(`/templates/${template.id}/metadata`, metadataPayload(meta));
      await api.put(`/templates/${template.id}/mapping`, { name, fields });
      if (meta.scope === "organization") {
        router.push(`/templates/${template.id}`);
      } else if (contractId) {
        await api.post(`/contracts/${contractId}/documents`, { template_id: template.id });
        router.push(`/contracts/${contractId}`);
      } else {
        router.push("/templates");
      }
    } catch (e) {
      setError((e as Error).message);
      setSaving(false);
    }
  };

  const stage = template ? 3 : uploading ? 1 : 0;
  const mapped = fields.filter((f) => f.field_key).length;
  const maskedText = analysis && Object.entries(analysis.masked).map(([k, v]) => `${k} ${v}건`).join(", ");

  return (
    <>
      <PageHeader
        back={contractId ? { href: `/contracts/${contractId}`, label: "계약으로 돌아가기" } : { href: "/templates", label: "양식 라이브러리" }}
        title={meta.scope === "organization" ? "기관·기업 지정 양식 등록" : "내 양식 업로드"}
        desc="기업마다 다른 항목명(총 용역대금 · 지급 예정 금액 · 용역 수행비)을 AI가 의미로 이해해 표준 데이터에 연결합니다."
      />
      <Card className="mb-5 p-5"><LibraryMetadataEditor value={meta} onChange={setMeta} admin={admin} /></Card>

      <ol className="mb-5 flex flex-wrap gap-2 text-[13px]">
        {STAGES.map((s, i) => (
          <li key={s} className={`rounded-full px-3 py-1 font-medium ${i < stage ? "bg-emerald-50 text-emerald-700" : i === stage ? "bg-primary text-white" : "bg-gray-100 text-muted"}`}>
            {i < stage ? "✓" : i + 1} {s}
          </li>
        ))}
      </ol>

      {!template && (
        <div
          className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed bg-surface px-6 py-16 text-center transition ${drag ? "border-primary bg-primary-soft" : "border-line"}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDrag(true);
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={onDrop}
        >
          <div className="flex flex-col items-center">
            {uploading ? (
              <>
                <Spinner />
                <p className="mt-3 text-sm">표·항목 구조를 분석하고 표준 데이터와 연결하는 중…</p>
              </>
            ) : (
              <>
                <p className="text-lg font-semibold">한글·Word·PDF 양식을 끌어다 놓으세요</p>
                <p className="mt-1 text-sm text-muted">HWP · HWPX · DOCX · PDF, 최대 10MB</p>
                <p className="mt-2 max-w-lg text-xs text-muted">한글·Word는 원본 양식의 입력 칸을 채웁니다. HWP는 HWPX로 변환해 작성하며, PDF는 항목 기반 Word로 재구성됩니다.</p>
                <Button className="mt-5" onClick={() => inputRef.current?.click()}>
                  파일 선택
                </Button>
                <input
                  ref={inputRef}
                  type="file"
                  accept=".hwp,.hwpx,.docx,.pdf"
                  hidden
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) upload(f);
                  }}
                />
                <p className="mt-6 max-w-md text-xs text-muted">
                  🔒 연락처·이메일·계좌번호 등은 AI 전송 전에 마스킹되며, 원본 전체가 아닌 항목명과 주변 문맥만 전송됩니다. 원본 파일은 보관기간 후 자동 삭제됩니다.
                </p>
              </>
            )}
          </div>
        </div>
      )}

      <div className="mt-4">
        <ErrorText>{error}</ErrorText>
      </div>

      {template && analysis && (
        <div className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-4">
            <Stat label="찾은 입력 칸" value={`${analysis.detected}개`} />
            <Stat label="자동 연결" value={`${mapped} / ${fields.length}`} tone={mapped === fields.length ? "green" : "amber"} />
            <Stat label="분석 방식" value={analysis.mode} small />
            <Stat label="AI 전송 정보" value={analysis.ai_used ? `${analysis.sent_chars}자 · 마스킹 ${maskedText || "0건"}` : "외부 전송 없음"} small />
          </div>

          <Card>
            <CardHeader
              title="항목 매핑 확인"
              desc="모양이 아니라 의미로 연결했습니다. 틀린 연결은 바꾸고, 필요 없는 칸은 ‘연결 안 함’으로 두세요."
              action={<Badge tone="indigo">{analysis.title || template.name}</Badge>}
            />
            <MappingEditor fields={fields} standard={standard} onChange={setFields} />
            {fields.length === 0 && <p className="px-5 pb-5 text-sm text-amber-700">자동으로 찾은 입력 칸이 없습니다. 항목명 오른쪽에 빈 셀을 두거나, 문단에 ‘계약명 : ____’ 또는 ‘&#123;&#123;contract_title&#125;&#125;’ 표시자를 넣은 뒤 다시 업로드하세요.</p>}
          </Card>

          <Card className="flex flex-wrap items-end justify-between gap-4 p-5">
            <div className="w-full max-w-sm">
              <Field label="양식 이름">
                <Input value={name} onChange={(e) => setName(e.target.value)} />
              </Field>
            </div>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                onClick={() => {
                  setTemplate(null);
                  setAnalysis(null);
                }}
              >
                다른 파일
              </Button>
              <Button onClick={save} loading={saving}>
                {meta.scope === "organization" ? "저장하고 공개 검토 →" : contractId ? "저장하고 이 계약에 서류 추가 →" : "양식 저장"}
              </Button>
            </div>
          </Card>
        </div>
      )}
    </>
  );
}

function Stat({ label, value, tone, small }: { label: string; value: string; tone?: "green" | "amber"; small?: boolean }) {
  const color = tone === "green" ? "text-emerald-600" : tone === "amber" ? "text-amber-600" : "";
  return (
    <Card className="px-4 py-3">
      <div className="text-xs text-muted">{label}</div>
      <div className={`mt-1 font-semibold ${small ? "text-sm" : "text-xl"} ${color}`}>{value}</div>
    </Card>
  );
}
