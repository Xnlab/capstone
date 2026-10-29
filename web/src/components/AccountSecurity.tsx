"use client";

import { useEffect, useState, type FormEvent } from "react";
import { api, clearSession } from "@/lib/api";
import { Button, Card, ErrorText, Field, Input } from "./ui";

type Status = { enabled: boolean; recovery_remaining: number };
type Setup = { secret: string; issuer: string; account: string };

export default function AccountSecurity({ onChanged }: { onChanged?: () => Promise<void> }) {
  const [status, setStatus] = useState<Status | null>(null);
  const [setup, setSetup] = useState<Setup | null>(null);
  const [codes, setCodes] = useState<string[]>([]);
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [disableAck, setDisableAck] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  useEffect(() => {
    let active = true;
    api.get<Status>("/auth/mfa").then(result => { if (active) setStatus(result); }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, []);

  const perform = async (action: "setup" | "enable" | "disable" | "recovery" | "password") => {
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await api.post<Setup & { recovery_codes?: string[] }>(action === "password" ? "/auth/password" : `/auth/mfa/${action}`, { password, code, ...(action === "password" ? { new_password: newPassword } : {}) });
      if (action === "setup") { setSetup(result); setCodes([]); }
      else {
        clearSession(); // Mutations rotate the session; never reuse the old CSRF token.
        setSetup(null); setCodes(result.recovery_codes ?? []);
        setPassword(""); setCode(""); setNewPassword(""); setConfirmation(""); setDisableAck(false);
        setMessage("변경을 완료하고 기존 로그인 세션을 폐기했습니다. 현재 기기는 새 세션으로 연결됩니다.");
        setStatus(await api.get<Status>("/auth/mfa"));
        await onChanged?.();
      }
    } catch (e) { setCode(""); setError((e as Error).message); }
    finally { setBusy(false); }
  };
  const passwordSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (newPassword !== confirmation) { setError("새 비밀번호가 일치하지 않습니다."); return; }
    void perform("password");
  };

  return <Card className="mb-5 space-y-4 p-5">
    <h2 className="font-semibold">계정 보호 · 2단계 인증</h2>
    <ErrorText>{error}</ErrorText>
    {message && <p role="status" className="text-sm text-green-700">{message}</p>}
    <p className="text-sm text-muted">{status ? status.enabled ? `2단계 인증 사용 중 · 남은 복구 코드 ${status.recovery_remaining}개` : "2단계 인증 미설정" : "보안 설정을 확인하고 있습니다."}</p>
    <p className="text-sm text-muted">인증 앱을 설정하면 로그인과 인감·민감 작업 승인에 추가 코드가 필요합니다. 코드 재사용은 차단되므로 다음 30초의 새 코드를 사용하세요.</p>
    <Field label="현재 비밀번호" required><Input type="password" autoComplete="current-password" maxLength={100} value={password} disabled={busy} onChange={e => setPassword(e.target.value)} /></Field>
    {(status?.enabled || setup) && <Field label="인증 앱 코드 또는 복구 코드" required><Input autoComplete="one-time-code" maxLength={40} value={code} disabled={busy} onChange={e => setCode(e.target.value)} /></Field>}
    {setup && <div className="space-y-3 rounded-lg border border-line p-4">
      <p className="text-sm">인증 앱에서 계정을 수동으로 추가하세요. 시간 기반(TOTP), 6자리, 30초, SHA1 설정입니다. 등록 키는 다른 사람에게 공유하지 마세요.</p>
      <p className="text-sm">서비스: {setup.issuer} · 계정: {setup.account}</p>
      <label htmlFor="mfa-setup-secret" className="block text-sm">등록 키 (10분 동안 등록 가능)</label>
      <Input id="mfa-setup-secret" value={setup.secret} readOnly autoComplete="off" spellCheck={false} />
      <Button disabled={busy || !password || !/^\d{6}$/.test(code)} onClick={() => void perform("enable")}>인증 코드 확인 후 활성화</Button>
      <Button variant="secondary" disabled={busy} onClick={() => { setSetup(null); setCode(""); }}>등록 키 숨기기</Button>
    </div>}
    {status && !status.enabled && !setup && <Button disabled={busy || !password || codes.length > 0} onClick={() => void perform("setup")}>인증 앱 등록 시작</Button>}
    {codes.length > 0 && <div className="space-y-3 rounded-lg border border-amber-300 bg-amber-50 p-4">
      <p role="status" className="font-medium">복구 코드는 지금 한 번만 표시됩니다.</p>
      <p className="text-sm">각 코드는 한 번만 사용할 수 있습니다. 비밀번호 관리자 등 안전한 곳에 별도로 저장하세요. 인증 앱과 복구 코드를 모두 잃으면 자동 복구할 수 없습니다.</p>
      <pre className="overflow-x-auto text-sm">{codes.join("\n")}</pre>
      <Button variant="secondary" onClick={() => setCodes([])}>안전하게 저장했으며 화면에서 숨기기</Button>
    </div>}
    {status?.enabled && <div className="space-y-3">
      <Button variant="secondary" disabled={busy || !password || !code || codes.length > 0} onClick={() => void perform("recovery")}>기존 복구 코드 폐기 후 재발급</Button>
      <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={disableAck} disabled={busy} onChange={e => setDisableAck(e.target.checked)} />2단계 인증을 해제하면 비밀번호만으로 로그인할 수 있음을 이해했습니다.</label>
      <Button variant="danger" disabled={busy || !password || !code || !disableAck || codes.length > 0} onClick={() => void perform("disable")}>현재 인증을 확인하고 2단계 인증 해제</Button>
    </div>}
    <form onSubmit={passwordSubmit} className="space-y-3 border-t border-line pt-4">
      <h3 className="font-medium">비밀번호 변경</h3>
      <p className="text-sm text-muted">변경하면 기존 기기의 로그인과 민감 작업 승인이 모두 취소됩니다.</p>
      <Field label="새 비밀번호 (12자 이상)" required><Input type="password" autoComplete="new-password" minLength={12} maxLength={100} required value={newPassword} disabled={busy} onChange={e => setNewPassword(e.target.value)} /></Field>
      <Field label="새 비밀번호 확인" required><Input type="password" autoComplete="new-password" minLength={12} maxLength={100} required value={confirmation} disabled={busy} onChange={e => setConfirmation(e.target.value)} /></Field>
      <Button type="submit" disabled={busy || !password || !status || (status.enabled && !code) || codes.length > 0}>비밀번호 변경 및 기존 세션 폐기</Button>
    </form>
  </Card>;
}
