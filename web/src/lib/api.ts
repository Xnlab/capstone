const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const TOKEN_KEY = "cdoc_token";
let csrf: string | null = null;
let csrfRequest: Promise<string> | null = null;

export function clearSession() {
  csrf = null;
  csrfRequest = null;
  try { localStorage.removeItem(TOKEN_KEY); } catch {}
}

async function csrfToken() {
  if (csrf) return csrf;
  csrfRequest ??= fetch(`${BASE}/auth/csrf`, { credentials: "include", cache: "no-store" }).then(async res => {
    if (!res.ok) throw new ApiError(res.status, "다시 로그인하세요.");
    const body = await res.json();
    csrf = body.csrf_token;
    return body.csrf_token as string;
  }).finally(() => { csrfRequest = null; });
  return csrfRequest;
}

export type ReauthRequest = { scope: string; resolve: (grant: string) => void; reject: (error: Error) => void };
function requestReauth(scope: string): Promise<string> {
  return new Promise((resolve, reject) => window.dispatchEvent(new CustomEvent<ReauthRequest>("security:reauth", { detail: { scope, resolve, reject } })));
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request(path: string, init: RequestInit = {}, retried = false): Promise<Response> {
  const headers = new Headers(init.headers);
  try { localStorage.removeItem(TOKEN_KEY); } catch {}
  const method = init.method ?? "GET";
  if (!["GET", "HEAD", "OPTIONS"].includes(method) && !["/auth/login", "/auth/register", "/auth/mfa/verify"].includes(path)) {
    headers.set("X-CSRF-Token", await csrfToken());
  }
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const res = await fetch(`${BASE}${path}`, { ...init, headers, credentials: "include", cache: "no-store" });
  const scope = res.headers.get("X-Reauthentication-Scope");
  if (res.status === 403 && scope && !retried) {
    headers.set("X-Sensitive-Grant", await requestReauth(scope));
    return request(path, { ...init, headers }, true);
  }
  if (!res.ok) {
    let msg = `요청 실패 (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") msg = data.detail;
      else if (Array.isArray(data.detail)) msg = data.detail.map((d: { msg: string }) => d.msg).join(", ");
    } catch {}
    if (res.status === 401 && typeof window !== "undefined" && !path.startsWith("/auth/")) {
      clearSession();
      window.location.href = "/login";
    }
    throw new ApiError(res.status, msg);
  }
  return res;
}

export const api = {
  get: async <T>(path: string) => (await request(path)).json() as Promise<T>,
  post: async <T>(path: string, body?: unknown) =>
    (await request(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) })).json() as Promise<T>,
  put: async <T>(path: string, body: unknown) =>
    (await request(path, { method: "PUT", body: JSON.stringify(body) })).json() as Promise<T>,
  del: async <T>(path: string) => (await request(path, { method: "DELETE" })).json() as Promise<T>,
  upload: async <T>(path: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return (await request(path, { method: "POST", body: fd })).json() as Promise<T>;
  },
  /** 인증이 필요한 파일 다운로드: blob으로 받아 저장 */
  download: async (path: string, fallbackName: string) => {
    const res = await request(path);
    const cd = res.headers.get("Content-Disposition") ?? "";
    const m = cd.match(/filename\*=UTF-8''([^;]+)/);
    const name = m ? decodeURIComponent(m[1]) : fallbackName;
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    URL.revokeObjectURL(url);
  },
};

export const won = (n: number) => `${n.toLocaleString("ko-KR")}원`;
export const fmtDate = (s: string | null) => (s ? s.replaceAll("-", ". ") + "." : "-");
