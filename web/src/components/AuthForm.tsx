"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { api, clearSession } from "@/lib/api";
import { APP_NAME, Button, ErrorText, Field, Input } from "./ui";

export default function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const [form, setForm] = useState({ email: "", password: "", name: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [challenge, setChallenge] = useState("");
  const [code, setCode] = useState("");
  const isRegister = mode === "register";

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      clearSession();
      if (challenge) {
        await api.post('/auth/mfa/verify', { challenge, code });
      } else {
        const result = await api.post<{ mfa_required?: boolean; challenge?: string }>(`/auth/${mode}`, isRegister ? form : { email: form.email, password: form.password });
        setForm(previous => ({ ...previous, password: "" }));
        if (result.mfa_required && result.challenge) { setChallenge(result.challenge); return; }
      }
      router.replace(isRegister ? "/company?welcome=1" : "/dashboard");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <Link href="/" className="mb-8 flex items-center justify-center gap-2 font-semibold">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-sm font-bold text-white">AI</span>
          {APP_NAME}
        </Link>
        <form onSubmit={submit} className="space-y-4 rounded-xl border border-line bg-white p-6">
          <h1 className="text-lg font-bold">{isRegister ? "회원가입" : "로그인"}</h1>
          {!challenge && <>{isRegister && (
            <Field label="이름">
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="홍길동" />
            </Field>
          )}
          <Field label="이메일" required>
            <Input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="you@company.com" />
          </Field>
          <Field label="비밀번호" required hint={isRegister ? "6자 이상" : undefined}>
            <Input type="password" required minLength={6} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          </Field></>}
          {challenge && <Field label="인증 앱 코드 또는 복구 코드" required hint="6자리 코드는 한 번만 사용할 수 있습니다. 이미 사용했다면 다음 코드로 시도하세요.">
            <Input required autoComplete="one-time-code" maxLength={40} value={code} onChange={e => setCode(e.target.value)} autoFocus />
          </Field>}
          <ErrorText>{error}</ErrorText>
          <Button type="submit" loading={loading} className="w-full">
            {challenge ? "추가 인증 후 로그인" : isRegister ? "가입하고 시작하기" : "로그인"}
          </Button>
          {challenge && <Button type="button" variant="secondary" disabled={loading} onClick={() => { setChallenge(""); setCode(""); setError(""); }}>비밀번호부터 다시 입력</Button>}
        </form>
        <p className="mt-4 text-center text-sm text-muted">
          {isRegister ? "이미 계정이 있나요? " : "처음이신가요? "}
          <Link href={isRegister ? "/login" : "/register"} className="font-medium text-primary">
            {isRegister ? "로그인" : "회원가입"}
          </Link>
        </p>
      </div>
    </div>
  );
}
