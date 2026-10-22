"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useQueryParam, useStandardFields } from "@/lib/hooks";
import { useUnsavedChanges } from "@/lib/useUnsavedChanges";
import type { Doc, Template } from "@/lib/types";
import { Badge, Button, Card, CardHeader, ErrorText, Field, Input, Loading, PageHeader, Textarea } from "@/components/ui";

const LONG_FIELDS = new Set([
  "attachment_list",
  "staff_plan", "deliverables", "quality_plan",
  "description", "work_summary", "quote_items", "detail_items", "completion_details",
  "work_method", "work_schedule", "usage_purpose", "attendees", "activity_details", "activity_result",
]);
const DERIVED_HINT: Record<string, string> = {
  amount_korean: "계약금액에서 자동 계산됩니다",
  supply_amount: "계약금액 ÷ 1.1",
  vat: "계약금액 − 공급가액",
  period: "착수일 ~ 완료일",
  submit_date: "오늘 날짜",
};
const FIELD_HINT: Record<string, string> = {
  staff_plan: "실제 참여자 이름·직위·담당업무를 입력하세요. 공고에서 요구하는 자격·참여율도 확인하세요.",
  deliverables: "산출물명·수량·제출시기·파일 형식을 계약조건에 맞게 입력하세요.",
  quality_plan: "시험·검수 절차, 자료보안, 보고주기와 변경관리 절차를 입력하세요.",
  attachment_list: "실제로 첨부할 서류만 한 줄에 하나씩 입력하세요. 공고·계약조건에 맞춰 수정하세요.",
  quote_items: "한 줄에 하나씩 ‘품목|수량|단가|비고’ 형식으로 입력하세요",
  detail_items: "한 줄에 하나씩 ‘항목|수량|단가|비고’ 형식으로 입력하세요",
  payment_amount_korean: "청구금액을 저장하면 자동으로 다시 계산됩니다",
};

export default function DocumentEditor() {
  const { id, docId } = useParams<{ id: string; docId: string }>();
  const { labelOf } = useStandardFields();
  const [doc, setDoc] = useState<Doc | null>(null);
  const [template, setTemplate] = useState<Template | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [pages, setPages] = useState<{ data: string; width: number; height: number }[]>([]);
  const [previewLoading, setPreviewLoading] = useState(true);
  const [previewError, setPreviewError] = useState("");
  const focus = useQueryParam("focus");
  const [saving, setSaving] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [savedAt, setSavedAt] = useState<string>("");

  const loadPreview = useCallback(async () => {
    setPreviewLoading(true);
    setPreviewError("");
    try {
      const result = await api.get<{ pages: { data: string; width: number; height: number }[] }>(`/documents/${docId}/preview-pages`);
      setPages(result.pages);
    } catch (e) {
      setPages([]);
      setPreviewError((e as Error).message);
    } finally {
      setPreviewLoading(false);
    }
  }, [docId]);

  useEffect(() => {
    api.get<Doc>(`/documents/${docId}`).then((d) => {
      setDoc(d);
      setValues(d.values);
      api.get<Template>(`/templates/${d.template_id}`).then(setTemplate);
      loadPreview();
    });
  }, [docId, loadPreview]);

  useEffect(() => {
    if (focus) setTimeout(() => document.getElementById(`f-${focus}`)?.focus(), 300);
  }, [focus, doc]);

  // 자체 양식이면 원래 항목명("지급 예정 금액")도 함께 보여준다
  const originalLabels = useMemo(() => {
    const m: Record<string, string[]> = {};
    template?.fields.forEach((f) => {
      if (f.field_key) (m[f.field_key] ??= []).push(f.label);
    });
    return m;
  }, [template]);

  const dirty = doc && JSON.stringify(values) !== JSON.stringify(doc.values);
  const markSaved = useUnsavedChanges(Boolean(dirty));

  const save = async () => {
    setSaving(true);
    setError("");
    try {
      const d = await api.put<Doc>(`/documents/${docId}`, { values });
      setDoc(d);
      setValues(d.values);
      markSaved();
      await loadPreview();
      setSavedAt(new Date().toLocaleTimeString("ko-KR"));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const reapply = async () => {
    if (!confirm("회사·계약정보를 다시 적용합니다. 직접 수정한 값은 덮어써집니다. 계속할까요?")) return;
    setBusy("reapply");
    try {
      const d = await api.post<Doc>(`/documents/${docId}/reapply`);
      setDoc(d);
      setValues(d.values);
      await loadPreview();
    } finally {
      setBusy(null);
    }
  };

  const generate = async (key: string) => {
    setBusy(key);
    try {
      const r = await api.post<{ value: string; ai_used: boolean }>(`/documents/${docId}/generate/${key}`);
      setValues((v) => ({ ...v, [key]: r.value }));
      if (!r.ai_used) setError("API 키가 없어 기본 문장 틀로 생성했습니다. (OPENAI_API_KEY 설정 시 AI 작성)");
    } finally {
      setBusy(null);
    }
  };

  if (!doc) return <Loading />;

  const nativeLabel = doc.output_format === "xlsx" ? "Excel" : doc.output_format === "hwpx" ? "한글(HWPX)" : doc.output_format === "pdf" ? "원본 PDF" : "Word";
  const nativeExt = doc.output_format;
  const completed = doc.field_keys.filter(k => String(values[k] ?? "").trim()).length;

  return (
    <>
      <PageHeader
        back={{ href: `/contracts/${id}`, label: "계약으로 돌아가기" }}
        title={doc.title}
        desc={
          <span className="flex items-center gap-1.5">
            <Badge tone={doc.template_kind === "builtin" ? "gray" : "blue"}>{doc.template_kind === "builtin" ? "기본 양식" : "자체 양식"}</Badge>
            {doc.status === "reviewed" ? <Badge tone="green">검토 완료</Badge> : <Badge tone="amber">작성 중</Badge>}
          </span>
        }
        action={
          <>
            <Button variant="secondary" onClick={() => api.download(`/documents/${docId}/download?format=native`, `${doc.title}.${nativeExt}`)}>
              {nativeLabel}
            </Button>
            <Button variant="secondary" onClick={() => api.download(`/documents/${docId}/download?format=pdf`, `${doc.title}.pdf`)}>
              PDF
            </Button>
          </>
        }
      />

      <div className="grid min-w-0 gap-5 xl:grid-cols-[380px_minmax(0,1fr)]">
        <Card className="min-w-0 self-start">
          <CardHeader
            title="입력 항목"
            desc={`${doc.field_keys.length}개 중 ${completed}개 입력 완료`}
            action={
              <Button size="sm" variant="ghost" onClick={reapply} loading={busy === "reapply"}>
                정보 다시 적용
              </Button>
            }
          />
          <div className="max-h-[calc(100vh-280px)] space-y-4 overflow-y-auto p-5">
            {doc.field_keys.map((k) => {
              const missing = doc.missing.includes(k) && !values[k];
              const orig = originalLabels[k]?.filter((l) => l !== labelOf(k));
              return (
                <Field
                  key={k}
                  label={labelOf(k) + (orig?.length ? ` · 양식상 “${orig.join(", ")}”` : "")}
                  hint={missing ? "필수 항목이 비어 있습니다" : FIELD_HINT[k] ?? DERIVED_HINT[k]}
                >
                  <div className={`rounded-lg ${focus === k ? "ring-2 ring-amber-400 ring-offset-2" : ""}`}>
                    {LONG_FIELDS.has(k) ? (
                      <Textarea id={`f-${k}`} rows={4} value={values[k] ?? ""} onChange={(e) => setValues({ ...values, [k]: e.target.value })} />
                    ) : (
                      <Input
                        id={`f-${k}`}
                        value={values[k] ?? ""}
                        onChange={(e) => setValues({ ...values, [k]: e.target.value })}
                        className={missing ? "border-red-300" : ""}
                      />
                    )}
                  </div>
                  {k === "work_summary" && (
                    <Button size="sm" variant="secondary" className="mt-2" onClick={() => generate(k)} loading={busy === k}>
                      ✦ AI로 다시 작성
                    </Button>
                  )}
                </Field>
              );
            })}
          </div>
          <div className="flex items-center justify-between gap-3 border-t border-line px-5 py-3">
            <span className="text-xs text-muted">{dirty ? "저장하지 않은 변경사항" : savedAt && `저장됨 ${savedAt}`}</span>
            <Button onClick={save} loading={saving} disabled={!dirty}>
              저장하고 미리보기
            </Button>
          </div>
          {error && (
            <div className="px-5 pb-4">
              <ErrorText>{error}</ErrorText>
            </div>
          )}
        </Card>

        <div className="min-w-0">
          <div className="mb-2 flex items-center justify-between text-[13px] text-muted">
            <span>미리보기 (저장된 내용 기준)</span>
            {doc.template_kind === "uploaded" && template?.source_type === "pdf" && <span>{doc.output_format === "pdf" ? "원본 PDF의 검토된 입력 위치에 값을 채웁니다" : "PDF 양식은 분석된 항목으로 Word 문서를 재구성합니다"}</span>}
            {doc.template_kind === "uploaded" && (template?.source_type === "hwp" || template?.source_type === "hwpx") && <span>업로드한 한글 원본 양식 기준</span>}
          </div>
          <div className="space-y-5" aria-busy={previewLoading}>
            {previewLoading ? <Loading /> : previewError ? (
              <div className="rounded-xl border border-line bg-white p-5">
                <ErrorText>{previewError}</ErrorText>
                <Button variant="secondary" size="sm" className="mt-3" onClick={loadPreview}>미리보기 다시 불러오기</Button>
              </div>
            ) : pages.map((page, index) => (
              <figure key={index} className="mx-auto w-full max-w-[720px]">
                {/* Rasterized PDF pages preserve wrapping and page breaks at every viewport width. */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={page.data} width={page.width} height={page.height} alt={`${doc.title} 미리보기 ${index + 1}페이지`} className="block h-auto w-full bg-white shadow-sm" />
                <figcaption className="mt-2 text-center text-xs text-muted">{index + 1} / {pages.length} 페이지</figcaption>
              </figure>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
