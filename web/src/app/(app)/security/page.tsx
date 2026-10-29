"use client";

import { useEffect, useState } from "react";
import { api, clearSession } from "@/lib/api";
import { useRouter } from "next/navigation";
import { Badge, Button, Card, CardHeader, Empty, ErrorText, Loading, PageHeader } from "@/components/ui";

type Log = { id: number; action: string; detail: string; created_at: string };

const MEASURES = [
  { n: "01", t: "최소 수집", d: "문서 작성에 꼭 필요한 회사·계약 정보만 저장합니다." },
  { n: "02", t: "마스킹", d: "AI 전송 시 일부 개인정보 패턴을 가립니다. 영업기밀 전체를 자동 제거하는 기능은 아닙니다." },
  { n: "03", t: "외부 전송", d: "AI 연동 시 항목·문맥·검토 텍스트 일부가 전송됩니다. 인감 이미지는 전송하지 않습니다." },
  { n: "04", t: "접근 통제", d: "본인 회사의 계약·서류·양식만 조회할 수 있습니다." },
  { n: "05", t: "자동 삭제", d: "업로드한 원본 파일은 보관기간 후, 또는 요청 즉시 삭제합니다." },
];

const ACTION: Record<string, { label: string; tone: "indigo" | "green" | "blue" | "red" | "gray" }> = {
  ai_send: { label: "AI 전송", tone: "indigo" },
  ai_generate: { label: "AI 작성", tone: "green" },
  mail_send: { label: "메일 발송", tone: "blue" },
  file_delete: { label: "파일 삭제", tone: "red" },
  file_purge: { label: "자동 삭제", tone: "red" },
  login: { label: "로그인", tone: "blue" },
  login_failed: { label: "로그인 실패", tone: "red" },
  logout: { label: "로그아웃", tone: "gray" },
  logout_all: { label: "전체 로그아웃", tone: "gray" },
  reauth: { label: "작업 승인", tone: "green" },
  reauth_failed: { label: "재인증 실패", tone: "red" },
  sensitive_use: { label: "승인 사용", tone: "indigo" },
  document_download: { label: "문서 다운로드", tone: "blue" },
  document_export: { label: "묶음 다운로드", tone: "blue" },
  seal_upload: { label: "인감 등록", tone: "indigo" },
  seal_delete: { label: "인감 삭제", tone: "red" },
  data_delete: { label: "내 데이터 삭제", tone: "red" },
};

export default function SecurityPage() {
  const router = useRouter();
  const [sessions, setSessions] = useState<{created_at: string; expires_at: string; current: boolean}[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [logs, setLogs] = useState<Log[] | null>(null);
  useEffect(() => {
    api.get<Log[]>("/audit-logs").then(setLogs);
    api.get<typeof sessions>("/auth/sessions").then(setSessions).catch(e => setError(e.message));
  }, []);

  return (
    <>
      <PageHeader title="보안·처리 이력" desc="기업 문서의 민감정보를 어떻게 다루는지, 그리고 내 데이터가 언제 외부로 나갔는지 확인합니다." />
      <ErrorText>{error}</ErrorText>
      <Card className="mb-5 p-5">
        <h2 className="font-semibold">로그인 세션</h2>
        <p className="my-2 text-sm text-muted">활성 세션 {sessions.length}개 · 최대 8시간 후 만료 · 로그아웃하면 서버에서도 즉시 폐기됩니다.</p>
        {sessions.map((session, index) => <p key={index} className="mb-2 text-sm">{session.current ? "현재 접속" : "다른 접속"} · 로그인 {new Date(session.created_at + "Z").toLocaleString("ko-KR")}</p>)}
        <Button variant="secondary" disabled={busy} onClick={async () => {
          setBusy(true); setError("");
          try { await api.post("/auth/logout-all"); clearSession(); router.replace("/login"); }
          catch(e) { setError((e as Error).message); } finally { setBusy(false); }
        }}>모든 기기에서 로그아웃</Button>
      </Card>
      <Card className="mb-5 p-5">
        <h2 className="font-semibold">내 문서·인감 삭제</h2>
        <p className="my-3 text-sm text-muted">계약·작성 서류·개인 업로드 양식·회사정보·인감을 삭제합니다. 계정과 최소 보안 이력, 공개 양식은 유지됩니다. 제공업체 백업과 이미 다운로드·발송한 사본은 별도입니다.</p>
        <Button variant="danger" disabled={busy} onClick={async () => {
          setBusy(true); setError("");
          try { await api.del("/privacy/data"); router.replace("/dashboard"); }
          catch(e) { setError((e as Error).message); } finally { setBusy(false); }
        }}>비밀번호 확인 후 내 데이터 삭제</Button>
      </Card>
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
