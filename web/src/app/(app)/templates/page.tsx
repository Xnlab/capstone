"use client";

import Link from "next/link";
import Image from "next/image";
import OrganizationLibrary from "@/components/OrganizationLibrary";
import { FavoriteButton, useFavorites } from "@/components/TemplateExtras";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useStandardFields } from "@/lib/hooks";
import type { Template } from "@/lib/types";
import { Badge, Button, Card, CardHeader, Empty, ErrorText, Input, LinkButton, Loading, Modal, PageHeader } from "@/components/ui";

type PreviewPage = { data: string; width: number; height: number };
type Preview = { title: string; pages: PreviewPage[]; output_format: "hwpx" | "xlsx" | "docx" | "pdf" };

export default function TemplatesPage() {
  const [items, setItems] = useState<Template[] | null>(null);
  const [q, setQ] = useState("");
  const [section, setSection] = useState("common");
  const [admin, setAdmin] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [cat, setCat] = useState("전체");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [previewing, setPreviewing] = useState<number | null>(null);
  const [previewError, setPreviewError] = useState("");
  const { labelOf } = useStandardFields();
  const favorites = useFavorites();

  useEffect(() => {
    api.get<Template[]>("/templates?include_drafts=true").then(setItems).catch(e => setLoadError(e.message));
    api.get<{ is_admin: boolean }>("/templates/library-settings").then(s => setAdmin(s.is_admin)).catch(e => setLoadError(e.message));
  }, []);

  const builtin = useMemo(() => items?.filter((t) => t.kind === "builtin") ?? [], [items]);
  const mine = favorites.sort(items?.filter((t) => t.library.scope === "private") ?? []);
  const cats = ["전체", ...Array.from(new Set(builtin.map((t) => t.category)))];
  const shown = favorites.sort(builtin.filter(
    (t) => (cat === "전체" || t.category === cat) && (!q || [t.name, ...t.aliases, t.description].some((s) => s.includes(q))),
  ));

  const showPreview = async (t: Template) => {
    setPreviewing(t.id);
    setPreviewError("");
    try {
      setPreview(await api.get<Preview>(`/templates/${t.id}/preview-pages`));
    } catch (error) {
      setPreviewError((error as Error).message);
    } finally {
      setPreviewing(null);
    }
  };

  if (!items) return loadError ? <ErrorText>{loadError}</ErrorText> : <Loading />;

  return (
    <>
      <PageHeader
        title="양식 라이브러리"
        desc="공통 양식, 제출처 지정 양식, 내 양식을 구분해 관리합니다."
        action={<LinkButton href="/templates/upload">＋ 자체 양식 업로드</LinkButton>}
      />

      <div className="mb-5 flex flex-wrap gap-2" role="tablist" aria-label="양식 구분">{[["common", "공통 양식"], ["organization", "기관·기업 지정 양식"], ["private", "내 양식"]].map(([key, label]) => <button key={key} role="tab" aria-selected={section === key} onClick={() => setSection(key)} className={`rounded-lg px-4 py-2 text-sm ${section === key ? "bg-primary text-white" : "bg-white border border-line"}`}>{label}</button>)}</div>
      <ErrorText>{loadError}</ErrorText>
      <ErrorText>{favorites.error}</ErrorText>
      {section === "organization" && <OrganizationLibrary items={items} admin={admin} favorites={favorites} />}
      {section === "common" && <Card className="mb-6">
        <CardHeader title="서비스 기본 양식" desc="계약 과정에서 자주 요구되는 서류 — 이름이 달라도(착수신고서, 준공계 …) 찾아집니다." />
        <div className="flex flex-wrap items-center gap-2 border-b border-line px-5 py-3">
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="양식 이름 검색" className="max-w-xs" />
          {cats.map((c) => (
            <button
              key={c}
              onClick={() => setCat(c)}
              className={`rounded-full px-3 py-1 text-[13px] ${cat === c ? "bg-primary text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}
            >
              {c}
            </button>
          ))}
        </div>
        <div className="grid auto-rows-fr gap-4 p-5 sm:grid-cols-2 lg:grid-cols-3">
          {shown.map((t) => (
            <div key={t.id} className="flex h-full flex-col rounded-lg border border-line p-4">
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold"><FavoriteButton id={t.id} state={favorites} /> {t.name}</span>
                <div className="flex gap-1">
                  <Badge tone="indigo">{t.output_format === "xlsx" ? "Excel" : "한글"}</Badge>
                  <Badge>{t.category}</Badge>
                </div>
              </div>
              <p className="mt-1.5 text-[13px] text-gray-600">{t.description}</p>
              <p className="mt-2 text-xs text-muted">다른 이름: {t.aliases.join(", ")}</p>
              <div className="mt-3 flex flex-wrap gap-1">
                {t.field_keys.map((k) => (
                  <span key={k} className="rounded bg-gray-50 px-1.5 py-0.5 text-[11px] text-gray-500">
                    {labelOf(k)}
                  </span>
                ))}
              </div>
              <div className="mt-auto pt-4">
                <Button className="w-full" variant="secondary" size="sm" loading={previewing === t.id} onClick={() => showPreview(t)}>
                  미리보기
                </Button>
              </div>
            </div>
          ))}
        </div>
      </Card>}

      {section === "private" && <Card>
        <CardHeader title="내 양식" desc="공개되지 않는 개인 양식입니다. 업로드한 원본은 보관기간 후 삭제됩니다." />
        {mine.length === 0 ? (
          <Empty title="업로드한 양식이 없습니다" desc="발주처가 보낸 한글·Word·PDF 양식을 올리면 입력 항목을 분석합니다." action={<LinkButton href="/templates/upload">업로드하기</LinkButton>} />
        ) : (
          <ul className="divide-y divide-line">
            {mine.map((t) => (
              <li key={t.id} className="flex items-center px-3">
                <FavoriteButton id={t.id} state={favorites} />
                <Link href={`/templates/${t.id}`} className="flex flex-1 flex-wrap items-center justify-between gap-2 px-5 py-3.5 hover:bg-gray-50">
                  <div>
                    <div className="flex items-center gap-1.5 font-medium">
                      {t.name}
                      <Badge tone="blue">{t.kind === "custom" ? "맞춤 초안" : t.source_type?.toUpperCase()}</Badge>
                      {t.status === "analyzing" ? <Badge tone="amber">매핑 확인 필요</Badge> : <Badge tone="green">사용 가능</Badge>}
                    </div>
                    <div className="mt-0.5 text-xs text-muted">
                      항목 {t.fields.length}개 · 연결 {t.fields.filter((f) => f.field_key).length}개
                      {t.expires_at && ` · 원본 보관 ~ ${t.expires_at.slice(0, 10)}`}
                    </div>
                  </div>
                  <span className="text-sm text-primary">{t.kind === "custom" ? "구성 보기 →" : "매핑 보기 →"}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>}

      <Modal open={Boolean(preview)} onClose={() => setPreview(null)} title={`${preview?.title ?? "양식"} 미리보기`} className="max-w-5xl">
        {preview && (
          <>
            <div className="mb-3 flex items-center justify-between gap-3 text-xs text-muted">
              <span>샘플 데이터의 A4 PDF 배치입니다. 제출 전 한글·Excel에서 원본 배치를 확인하세요.</span>
              <Badge tone="indigo">실제 원본: {preview.output_format === "xlsx" ? "Excel(XLSX)" : "한글(HWPX)"}</Badge>
            </div>
            <div className="max-h-[78vh] space-y-4 overflow-auto rounded-lg border border-line bg-gray-200 p-4">
              {preview.pages.map((page, index) => (
                <div key={index} className="mx-auto max-w-[794px]">
                  <div className="mb-1 text-center text-[11px] text-muted">{index + 1} / {preview.pages.length} 페이지</div>
                  <Image
                    src={page.data}
                    alt={`${preview.title} ${index + 1}페이지`}
                    width={page.width}
                    height={page.height}
                    unoptimized
                    className="h-auto w-full bg-white shadow-lg"
                  />
                </div>
              ))}
            </div>
          </>
        )}
      </Modal>
      {previewError && (
        <div className="fixed bottom-5 right-5 z-50 max-w-md">
          <ErrorText>{previewError}</ErrorText>
        </div>
      )}
    </>
  );
}
