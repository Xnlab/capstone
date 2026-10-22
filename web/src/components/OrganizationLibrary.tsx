"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Template } from "@/lib/types";
import { FavoriteButton, PastNoticeBadge, useFavorites } from "./TemplateExtras";
import { Badge, Card, CardHeader, Empty, Input, LinkButton, ErrorText } from "@/components/ui";

type Source = { organization: string; name: string; format: string; url: string; note: string };

export default function OrganizationLibrary({ items, admin, favorites }: { items: Template[]; admin: boolean; favorites: ReturnType<typeof useFavorites> }) {
  const [q, setQ] = useState("");
  const [sources, setSources] = useState<Source[]>([]);
  const [error, setError] = useState("");
  useEffect(() => { api.get<Source[]>("/templates/sources").then(setSources).catch(e => setError(e.message)); }, []);
  const match = (text: string) => text.toLowerCase().includes(q.trim().toLowerCase());
  const shown = favorites.sort(items.filter(t => t.library.scope === "organization" && match([t.name, t.library.organization, t.library.document_type, t.library.version, t.library.project_code].join(" "))));
  return <div className="space-y-5">
    <Card>
      <CardHeader title="기관·기업 지정 양식" desc="제출처와 해당 사업의 버전을 확인한 뒤 사용하세요." action={admin ? <LinkButton href="/templates/upload?library=1">지정 양식 등록</LinkButton> : undefined} />
      <div className="p-5"><Input value={q} onChange={e => setQ(e.target.value)} placeholder="기관·기업명 / 서류 종류 / 버전 검색" /></div>
      {!shown.length ? <Empty title="공개된 지정 양식이 없습니다" desc="아래 수집 출처의 원본을 확보하고 매핑·출력 검토를 마치면 여기에 공개됩니다." /> :
        <div className="grid gap-4 p-5 sm:grid-cols-2 lg:grid-cols-3">{shown.map(t => <div key={t.id} className="rounded-lg border border-line p-4 hover:border-primary">
          <div className="flex items-start justify-between gap-2"><div className="flex flex-wrap gap-2"><Badge tone="blue">{t.library.organization}</Badge><Badge tone={t.status === "ready" ? "green" : "amber"}>{t.status === "ready" ? "공개 · 사용 가능" : "관리자 검토 중"}</Badge><PastNoticeBadge template={t} /></div><FavoriteButton id={t.id} state={favorites} /></div>
          <h3 className="mt-3 font-semibold"><Link href={`/templates/${t.id}`}>{t.name}</Link></h3>
          <p className="mt-2 text-xs text-muted">{t.library.document_type || "서류 종류 미입력"} · {t.library.version || "버전 미입력"}</p>
          {t.library.project_code && <p className="mt-1 text-xs text-muted">공고: {t.library.project_code}</p>}
          <Link href={`/templates/${t.id}`} className="mt-3 inline-block text-sm text-primary">출처·매핑·검토 보기 →</Link>
        </div>)}</div>}
    </Card>
    <Card>
      <CardHeader title="수집할 공식 양식 출처" desc="출처 목록입니다. 원본을 등록·검토하기 전에는 자동 작성에 사용되지 않습니다." />
      <ErrorText>{error}</ErrorText>
      <div className="grid gap-4 p-5 sm:grid-cols-2">{sources.filter(s => match(`${s.organization} ${s.name}`)).map(s => <div key={s.url} className="rounded-lg border border-line p-4">
        <div className="flex justify-between gap-2"><strong>{s.organization}</strong><Badge>{s.format}</Badge></div>
        <p className="mt-2 text-sm">{s.name}</p><p className="mt-2 text-xs text-muted">{s.note}</p>
        <a className="mt-3 inline-block text-sm text-primary" href={s.url} target="_blank" rel="noopener noreferrer">공식 출처 열기 ↗</a>
        {admin && <Link className="ml-4 text-sm text-primary" href={`/templates/upload?library=1&organization=${encodeURIComponent(s.organization)}&source=${encodeURIComponent(s.url)}`}>파일 확보 후 등록 →</Link>}
      </div>)}</div>
    </Card>
  </div>;
}
