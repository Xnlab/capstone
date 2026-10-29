"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, type ReauthRequest } from "@/lib/api";
import { Button, ErrorText, Input } from "./ui";

export default function ReauthDialog() {
  const [current, setCurrent] = useState<ReauthRequest | null>(null);
  const queue = useRef<ReauthRequest[]>([]);
  const active = useRef<ReauthRequest | null>(null);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const advance = () => {
    active.current = queue.current.shift() ?? null;
    setCurrent(active.current); setPassword(""); setError("");
  };
  useEffect(() => {
    const listener = (event: Event) => {
      queue.current.push((event as CustomEvent<ReauthRequest>).detail);
      if (!active.current) advance();
    };
    window.addEventListener("security:reauth", listener);
    return () => {
      window.removeEventListener("security:reauth", listener);
      active.current?.reject(new Error("재인증이 취소되었습니다."));
      queue.current.forEach(item => item.reject(new Error("재인증이 취소되었습니다.")));
      queue.current = []; active.current = null;
    };
  }, []);
  useEffect(() => {
    if (current) dialog.current?.showModal();
    else dialog.current?.close();
  }, [current]);
  const cancel = () => {
    if (busy) return;
    current?.reject(new Error("재인증을 취소했습니다.")); advance();
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!current) return;
    setBusy(true); setError("");
    try {
      const result = await api.post<{ grant: string }>("/auth/reauthenticate", { password, scope: current.scope });
      current.resolve(result.grant); advance();
    } catch (e) { setPassword(""); setError((e as Error).message); }
    finally { setBusy(false); }
  };
  return <dialog ref={dialog} onCancel={event => { event.preventDefault(); cancel(); }} aria-labelledby="reauth-title" className="m-auto w-full max-w-md rounded-xl border border-line bg-white p-6 shadow-xl backdrop:bg-black/40">
    <form onSubmit={submit}>
      <h2 id="reauth-title" className="text-lg font-semibold">민감 작업 확인</h2>
      <p className="my-3 text-sm text-muted">인감 열람·관리 또는 인감이 포함된 문서 출력·발송을 승인합니다. 이 승인은 요청한 작업에 한 번만 사용됩니다.</p>
      {current?.scope === "data:delete" && <p className="mb-3 text-sm text-red-700">내 계약·서류·개인 양식·회사정보·인감을 삭제합니다. 다운로드한 파일과 제공업체 백업은 별도입니다.</p>}
      <label htmlFor="reauth-password" className="text-sm">현재 비밀번호</label>
      <Input id="reauth-password" type="password" autoComplete="current-password" required value={password} onChange={event => setPassword(event.target.value)} disabled={busy} autoFocus />
      <ErrorText>{error}</ErrorText>
      <div className="mt-5 flex justify-end gap-2"><Button type="button" variant="secondary" onClick={cancel} disabled={busy}>취소</Button><Button type="submit" loading={busy}>이 작업 승인</Button></div>
    </form>
  </dialog>;
}
