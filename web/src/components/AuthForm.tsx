"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { api, setToken } from "@/lib/api";
import { APP_NAME, Button, ErrorText, Field, Input } from "./ui";

export default function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const [form, setForm] = useState({ email: "", password: "", name: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const isRegister = mode === "register";

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await api.post<{ access_token: string }>(`/auth/${mode}`, isRegister ? form : { email: form.email, password: form.password });
      setToken(res.access_token);
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
          {isRegister && (
            <Field label="이름">
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="홍길동" />
            </Field>
          )}
          <Field label="이메일" required>
            <Input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="you@company.com" />
          </Field>
          <Field label="비밀번호" required hint={isRegister ? "6자 이상" : undefined}>
            <Input type="password" required minLength={6} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          </Field>
          <ErrorText>{error}</ErrorText>
          <Button type="submit" loading={loading} className="w-full">
            {isRegister ? "가입하고 시작하기" : "로그인"}
          </Button>
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
