"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { api, getToken, setToken } from "@/lib/api";
import type { User } from "@/lib/types";
import { APP_NAME } from "./ui";

const NAV = [
  { href: "/dashboard", label: "내 계약", icon: "▦" },
  { href: "/contracts/new", label: "새 계약", icon: "＋" },
  { href: "/templates", label: "양식 라이브러리", icon: "▤" },
  { href: "/company", label: "회사 정보", icon: "◉" },
  { href: "/security", label: "보안·처리 이력", icon: "⛨" },
];

export default function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [health, setHealth] = useState<{ ai_mode: string; mail_mode: string; cloud_mode?: boolean } | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    api.get<User>("/auth/me").then(setUser).catch(() => {});
    api.get<{ ai_mode: string; mail_mode: string; cloud_mode?: boolean }>("/health").then(setHealth).catch(() => {});
  }, [router]);

  const logout = () => {
    setToken(null);
    router.replace("/login");
  };

  const isActive = (href: string) =>
    href === "/dashboard" ? pathname === "/dashboard" || (pathname.startsWith("/contracts/") && pathname !== "/contracts/new") : pathname.startsWith(href);

  if (!user) return <div className="min-h-screen" />;

  return (
    <div className="min-h-screen lg:flex">
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-60 shrink-0 border-r border-line bg-white transition-transform lg:sticky lg:top-0 lg:h-screen lg:translate-x-0 ${
          menuOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-16 items-center gap-2 border-b border-line px-5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-sm font-bold text-white">AI</span>
          <span className="text-[14px] leading-tight font-semibold">{APP_NAME}</span>
        </div>
        <nav className="space-y-0.5 p-3">
          {NAV.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              onClick={() => setMenuOpen(false)}
              className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm ${
                isActive(n.href) ? "bg-primary-soft font-semibold text-primary" : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              <span className="w-4 text-center">{n.icon}</span>
              {n.label}
            </Link>
          ))}
        </nav>
        {health && (
          <div className="absolute bottom-16 left-3 right-3 rounded-lg bg-gray-50 px-3 py-2 text-xs text-muted">
            <div>AI: {health.ai_mode === "llm" ? "LLM 연동" : "규칙 기반(키 미설정)"}</div>
            <div>메일: {health.mail_mode === "smtp" ? "SMTP 발송" : "MOCK(발송 안 함)"}</div>
          </div>
        )}
        <div className="absolute bottom-0 left-0 right-0 flex items-center justify-between border-t border-line px-4 py-3 text-sm">
          <span className="truncate text-muted">{user.name || user.email}</span>
          <button onClick={logout} className="text-muted hover:text-foreground">
            로그아웃
          </button>
        </div>
      </aside>
      {menuOpen && <div className="fixed inset-0 z-30 bg-black/20 lg:hidden" onClick={() => setMenuOpen(false)} />}

      <div className="min-w-0 flex-1">
        <header className="flex h-14 items-center gap-3 border-b border-line bg-white px-4 lg:hidden">
          <button onClick={() => setMenuOpen(true)} className="text-xl" aria-label="메뉴">
            ☰
          </button>
          <span className="font-semibold">{APP_NAME}</span>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-6 sm:px-8 sm:py-8">
          {health?.cloud_mode && <div role="note" className="mb-5 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-900">무료 체험 버전 · 업로드는 파일당 3MB, 계정당 20개입니다. HWP는 HWPX로 저장 후 업로드하세요. 기본 양식 미리보기는 지원하며, 업로드한 한글 양식은 HWPX 다운로드로 확인하세요. AI는 규칙 기반이며 메일은 실제 발송되지 않습니다. 실제 민감정보 입력은 피해주세요.</div>}
          {children}
        </main>
      </div>
    </div>
  );
}
