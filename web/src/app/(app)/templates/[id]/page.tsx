"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useStandardFields } from "@/lib/hooks";
import type { LibraryMetadata, Template, TemplateField } from "@/lib/types";
import MappingEditor from "@/components/MappingEditor";
import LibraryMetadataEditor, { metadataPayload } from "@/components/LibraryMetadataEditor";
import { PastNoticeBadge } from "@/components/TemplateExtras";
import { useUnsavedChanges } from "@/lib/useUnsavedChanges";
import { Badge, Button, Card, CardHeader, ErrorText, Input, Loading, PageHeader } from "@/components/ui";

export default function TemplateDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { fields: standard } = useStandardFields();
  const [t, setT] = useState<Template | null>(null);
  const [fields, setFields] = useState<TemplateField[]>([]);
  const [meta, setMeta] = useState<LibraryMetadata>({ scope: "private" });
  const [settings, setSettings] = useState({ is_admin: false, user_id: 0 });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [preview, setPreview] = useState("");
  const [name, setName] = useState("");
  const [checks, setChecks] = useState({ mapping_checked: false, output_checked: false, rights_checked: false });
  useEffect(() => {
    Promise.all([api.get<Template>(`/templates/${id}`), api.get<typeof settings>("/templates/library-settings")]).then(([x, s]) => {
      setT(x); setName(x.name); setFields(x.fields); setMeta(x.library); setSettings(s);
    }).catch(e => setError(e.message));
  }, [id]);
  const editable = !!t && (t.library.scope === "organization" ? settings.is_admin : t.owner_id === settings.user_id);
  const dirty = !!t && (name !== t.name || JSON.stringify(meta) !== JSON.stringify(t.library) || JSON.stringify(fields) !== JSON.stringify(t.fields));
  useUnsavedChanges(dirty);
  const act = async (fn: () => Promise<void>) => {
    setBusy(true); setError(""); setMessage("");
    try { await fn(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  const save = () => act(async () => {
    await api.put(`/templates/${id}/metadata`, metadataPayload(meta));
    const x = await api.put<Template>(`/templates/${id}/mapping`, { fields });
    setT(x); setMeta(x.library); setChecks({ mapping_checked: false, output_checked: false, rights_checked: false }); setPreview("");
    setMessage(x.library.scope === "organization" ? "저장했습니다. 출력과 이용 조건을 확인한 뒤 공개하세요." : "저장했습니다.");
  });
  if (!t) return error ? <ErrorText>{error}</ErrorText> : <Loading />;
  if (t.kind === "builtin") return <p>공통 양식은 라이브러리에서 미리볼 수 있습니다.</p>;
  return <>
    <PageHeader back={{ href: "/templates", label: "양식 라이브러리" }} title={t.name} desc={t.description} action={editable ? <Button variant="danger" onClick={() => {
      if (confirm("이 양식과 원본 파일을 삭제할까요?")) act(async () => { await api.del(`/templates/${id}`); router.replace("/templates"); });
    }}>양식 삭제</Button> : undefined} />
    <ErrorText>{error}</ErrorText>{message && <p role="status" className="mb-4 text-sm text-emerald-700">{message}</p>}
    {editable && <Card className="mb-5 flex flex-wrap items-center gap-3 p-5"><label htmlFor="template-name" className="text-sm font-medium">양식 이름</label><Input id="template-name" className="max-w-md" maxLength={100} value={name} onChange={e => setName(e.target.value)} /><Button variant="secondary" loading={busy} disabled={!name.trim() || name.trim() === t.name} onClick={() => act(async () => {
      const renamed = await api.put<Template>(`/templates/${id}/name`, { name });
      setT(renamed); setName(renamed.name); setMessage("양식 이름을 변경했습니다. 기존 작성 서류의 제목은 유지됩니다.");
    })}>이름 변경</Button></Card>}
    <Card className="mb-5 p-5">
      <div className="mb-4 flex flex-wrap gap-2"><Badge>{t.library.scope === "organization" ? "기관·기업 지정 양식" : "내 업로드 양식"}</Badge><Badge tone={t.status === "ready" ? "green" : "amber"}>{t.status === "ready" ? "사용 가능" : "검토 필요"}</Badge><PastNoticeBadge template={t} /></div>
      {editable ? <LibraryMetadataEditor value={meta} onChange={v => { setMeta(v); setChecks({ mapping_checked: false, output_checked: false, rights_checked: false }); }} admin={settings.is_admin} /> : <div className="space-y-2 text-sm">
        <p>발주처: {meta.organization} · 서류: {meta.document_type}</p><p>버전: {meta.version} · 게시일: {meta.source_date || "미기재"}</p>
        {meta.project_code && <p>공고·사업번호: {meta.project_code}</p>}<p>이용 조건: {meta.usage_terms}</p>
      </div>}
      <div className="mt-4 flex flex-wrap gap-4 text-sm">
        {t.library.source_url && <a href={t.library.source_url} target="_blank" rel="noopener noreferrer" className="text-primary">출처 열기 ↗</a>}
        <Button size="sm" variant="secondary" onClick={() => act(async () => { await api.download(`/templates/${id}/original`, `${t.name}.${t.source_type}`); })}>보관 원본 다운로드</Button>
        <Button size="sm" variant="secondary" onClick={() => act(async () => { await api.download(`/templates/${id}/sample-file`, `샘플.${t.output_format}`); })}>샘플 출력 다운로드</Button>
      </div>
      {t.source_type === "pdf" && <p className="mt-3 text-xs text-amber-700">{t.output_format === "pdf" ? "입력 위치가 검토된 PDF입니다. 원본 표·본문은 유지하고 지정된 입력란만 채웁니다. 인감·서명은 직접 확인하세요." : "입력 위치가 없는 PDF는 Word로 재구성됩니다. 원본을 유지하려면 PDF 입력 위치 검토가 필요합니다."}</p>}
    </Card>
    <Card>
      <CardHeader title="입력 칸 매핑" desc="고정 문구는 원본에 유지하고 입력 칸만 표준 필드에 연결합니다." />
      {editable ? <MappingEditor fields={fields} standard={standard} onChange={v => { setFields(v); setChecks({ mapping_checked: false, output_checked: false, rights_checked: false }); }} /> :
        <div className="flex flex-wrap gap-2 p-5">{fields.map((f, i) => <Badge key={i}>{f.label}</Badge>)}</div>}
      <div className="flex flex-wrap justify-end gap-3 border-t border-line p-5">
        <Button variant="secondary" loading={busy} onClick={() => act(async () => { setPreview((await api.get<{ html: string }>(`/templates/${id}/review-preview`)).html); })}>저장된 양식 샘플 미리보기</Button>
        {editable && <Button loading={busy} onClick={save}>정보·매핑 저장</Button>}
      </div>
    </Card>
    {preview && <Card className="my-5 p-5"><h2 className="mb-4 font-semibold">샘플 데이터 미리보기</h2><div className="overflow-auto" dangerouslySetInnerHTML={{ __html: preview }} /><p className="mt-4 text-xs text-muted">서식·페이지 배치는 다운로드한 샘플 파일에서도 확인하세요.</p></Card>}
    {editable && meta.scope === "organization" && <Card className="mt-5 p-5">
      <h2 className="font-semibold">관리자 공개 검토</h2><p className="mt-2 text-sm text-muted">먼저 저장한 뒤 샘플과 출력 파일을 확인하세요. 수정하면 공개 상태가 해제됩니다.</p>
      <div className="my-4 space-y-2">{([["mapping_checked", "입력 칸 매핑과 고정 문구를 확인했습니다"], ["output_checked", "미리보기·출력 파일의 서식을 확인했습니다"], ["rights_checked", "출처·이용 조건·적용 버전을 확인했습니다"]] as const).map(([key, label]) => <label className="block text-sm" key={key}><input type="checkbox" checked={checks[key]} onChange={e => setChecks({ ...checks, [key]: e.target.checked })} className="mr-2" />{label}</label>)}</div>
      {dirty && <p className="mb-3 text-sm text-amber-700">수정한 내용을 먼저 저장하세요.</p>}
      <Button loading={busy} disabled={dirty || !Object.values(checks).every(Boolean)} onClick={() => act(async () => {
        const x = await api.post<Template>(`/templates/${id}/publish`, checks); setT(x); setMeta(x.library); setMessage("지정 양식을 라이브러리에 공개했습니다.");
      })}>검토 완료·공개</Button>
    </Card>}
  </>;
}
