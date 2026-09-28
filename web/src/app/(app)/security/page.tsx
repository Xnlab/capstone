"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Badge, Card, CardHeader, Empty, Loading, PageHeader } from "@/components/ui";

type Log = { id: number; action: string; detail: string; created_at: string };

const MEASURES = [
  { n: "01", t: "최소 수집", d: "문서 작성에 꼭 필요한 회사·계약 정보만 저장합니다." },
  { n: "02", t: "마스킹", d: "전화번호·이메일·계좌번호·주민번호는 AI 전송 전에 비식별화합니다." },
  { n: "03", t: "최소 전송", d: "원본 전체가 아니라 항목명과 짧은 문맥만 AI에 전달합니다." },
  { n: "04", t: "접근 통제", d: "본인 회사의 계약·서류·양식만 조회할 수 있습니다." },
  { n: "05", t: "자동 삭제", d: "업로드한 원본 파일은 보관기간 후, 또는 요청 즉시 삭제합니다." },
];

const ACTION: Record<string, { label: string; tone: "indigo" | "green" | "blue" | "red" | "gray" }> = {
  ai_send: { label: "AI 전송", tone: "indigo" },
  ai_generate: { label: "AI 작성", tone: "green" },
  mail_send: { label: "메일 발송", tone: "blue" },
  file_delete: { label: "파일 삭제", tone: "red" },
  file_purge: { label: "자동 삭제", tone: "red" },
};

export default function SecurityPage() {
  const [logs, setLogs] = useState<Log[] | null>(null);
  useEffect(() => {
    api.get<Log[]>("/audit-logs").then(setLogs);
  }, []);

  return (
    <>
      <PageHeader title="보안·처리 이력" desc="기업 문서의 민감정보를 어떻게 다루는지, 그리고 내 데이터가 언제 외부로 나갔는지 확인합니다." />
      <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {MEASURES.map((m) => (
          <Card key={m.n} className="p-4">
            <div className="text-xs font-bold text-primary">{m.n}</div>
            <div className="mt-1 font-semibold">{m.t}</div>
            <p className="mt-1 text-[13px] leading-relaxed text-gray-600">{m.d}</p>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader title="내 데이터 처리 이력" desc="최근 100건" />
        {logs === null ? (
          <Loading />
        ) : logs.length === 0 ? (
          <Empty title="아직 기록이 없습니다" desc="AI 전송, 메일 발송, 파일 삭제가 일어나면 여기에 남습니다." />
        ) : (
          <ul className="divide-y divide-line">
            {logs.map((l) => {
              const a = ACTION[l.action] ?? { label: l.action, tone: "gray" as const };
              return (
                <li key={l.id} className="flex flex-wrap items-center gap-3 px-5 py-3 text-sm">
                  <Badge tone={a.tone}>{a.label}</Badge>
                  <span className="flex-1">{l.detail}</span>
                  <span className="text-xs text-muted">{new Date(l.created_at + "Z").toLocaleString("ko-KR")}</span>
                </li>
              );
            })}
          </ul>
        )}
      </Card>
    </>
  );
}
