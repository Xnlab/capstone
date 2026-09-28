"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useStandardFields } from "@/lib/hooks";
import type { Template } from "@/lib/types";
import { Badge, Card, CardHeader, Empty, Input, LinkButton, Loading, PageHeader } from "@/components/ui";

export default function TemplatesPage() {
  const [items, setItems] = useState<Template[] | null>(null);
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("전체");
  const { labelOf } = useStandardFields();

  useEffect(() => {
    api.get<Template[]>("/templates").then(setItems);
  }, []);

  const builtin = useMemo(() => items?.filter((t) => t.kind === "builtin") ?? [], [items]);
  const mine = items?.filter((t) => t.kind === "uploaded") ?? [];
  const cats = ["전체", ...Array.from(new Set(builtin.map((t) => t.category)))];
  const shown = builtin.filter(
    (t) => (cat === "전체" || t.category === cat) && (!q || [t.name, ...t.aliases, t.description].some((s) => s.includes(q))),
  );

  if (!items) return <Loading />;

  return (
    <>
      <PageHeader
        title="양식 라이브러리"
        desc="서비스 기본 양식과 우리 회사가 올린 자체 양식을 관리합니다."
        action={<LinkButton href="/templates/upload">＋ 자체 양식 업로드</LinkButton>}
      />

      <Card className="mb-6">
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
        <div className="grid gap-4 p-5 sm:grid-cols-2 lg:grid-cols-3">
          {shown.map((t) => (
            <div key={t.id} className="rounded-lg border border-line p-4">
              <div className="flex items-center justify-between">
                <span className="font-semibold">{t.name}</span>
                <Badge>{t.category}</Badge>
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
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <CardHeader title="우리 회사 자체 양식" desc="업로드한 원본 파일은 보관기간이 지나면 자동 삭제됩니다." />
        {mine.length === 0 ? (
          <Empty title="업로드한 양식이 없습니다" desc="발주처가 보낸 Word/PDF 양식을 올리면 AI가 항목을 분석합니다." action={<LinkButton href="/templates/upload">업로드하기</LinkButton>} />
        ) : (
          <ul className="divide-y divide-line">
            {mine.map((t) => (
              <li key={t.id}>
                <Link href={`/templates/${t.id}`} className="flex flex-wrap items-center justify-between gap-2 px-5 py-3.5 hover:bg-gray-50">
                  <div>
                    <div className="flex items-center gap-1.5 font-medium">
                      {t.name}
                      <Badge tone="blue">{t.source_type?.toUpperCase()}</Badge>
                      {t.status === "analyzing" ? <Badge tone="amber">매핑 확인 필요</Badge> : <Badge tone="green">사용 가능</Badge>}
                    </div>
                    <div className="mt-0.5 text-xs text-muted">
                      항목 {t.fields.length}개 · 연결 {t.fields.filter((f) => f.field_key).length}개
                      {t.expires_at && ` · 원본 보관 ~ ${t.expires_at.slice(0, 10)}`}
                    </div>
                  </div>
                  <span className="text-sm text-primary">매핑 보기 →</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}
