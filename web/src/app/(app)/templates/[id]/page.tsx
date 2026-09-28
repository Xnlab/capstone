"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useStandardFields } from "@/lib/hooks";
import type { Template, TemplateField } from "@/lib/types";
import MappingEditor from "@/components/MappingEditor";
import { Badge, Button, Card, CardHeader, ErrorText, Loading, PageHeader } from "@/components/ui";

export default function TemplateDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { fields: standard } = useStandardFields();
  const [t, setT] = useState<Template | null>(null);
  const [fields, setFields] = useState<TemplateField[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.get<Template>(`/templates/${id}`).then((x) => {
      setT(x);
      setFields(x.fields);
    });
  }, [id]);

  const save = async () => {
    setSaving(true);
    setError("");
    try {
      const x = await api.put<Template>(`/templates/${id}/mapping`, { fields });
      setT(x);
      setFields(x.fields);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!confirm("양식과 업로드한 원본 파일을 즉시 삭제합니다. 계속할까요?")) return;
    try {
      await api.del(`/templates/${id}`);
      router.replace("/templates");
    } catch (e) {
      setError((e as Error).message);
    }
  };

  if (!t) return <Loading />;
  if (t.kind === "builtin") {
    router.replace("/templates");
    return null;
  }

  return (
    <>
      <PageHeader
        back={{ href: "/templates", label: "양식 라이브러리" }}
        title={t.name}
        desc={t.description}
        action={
          <Button variant="danger" onClick={remove}>
            양식·원본 삭제
          </Button>
        }
      />
      <Card>
        <CardHeader
          title="항목 매핑"
          desc={t.expires_at ? `원본 파일 보관 기한: ${t.expires_at.slice(0, 10)} (이후 자동 삭제, 매핑 정보는 유지)` : undefined}
          action={t.status === "analyzing" ? <Badge tone="amber">확인 필요</Badge> : <Badge tone="green">사용 가능</Badge>}
        />
        <MappingEditor fields={fields} standard={standard} onChange={setFields} />
        <div className="flex items-center justify-end gap-3 border-t border-line px-5 py-4">
          <ErrorText>{error}</ErrorText>
          {saved && <span className="text-sm text-emerald-600">저장되었습니다 ✓</span>}
          <Button onClick={save} loading={saving}>
            매핑 저장
          </Button>
        </div>
      </Card>
    </>
  );
}
