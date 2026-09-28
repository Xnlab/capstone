"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { api } from "./api";
import type { StandardField } from "./types";

let cache: StandardField[] | null = null;

/** 표준 필드 사전 (key → 한글명). 앱 전체에서 한 번만 불러온다. */
export function useStandardFields() {
  const [fields, setFields] = useState<StandardField[]>(cache ?? []);
  useEffect(() => {
    if (cache) return;
    api.get<StandardField[]>("/templates/standard-fields").then((f) => {
      cache = f;
      setFields(f);
    });
  }, []);
  const labelOf = (key: string | null) => (key ? fields.find((f) => f.key === key)?.label ?? key : "-");
  return { fields, labelOf };
}

const noopSubscribe = () => () => {};

/** URL 쿼리 파라미터 읽기 (Suspense 경계 없이 클라이언트에서만 읽음, 서버 렌더 시 null) */
export function useQueryParam(name: string): string | null {
  return useSyncExternalStore(
    noopSubscribe,
    () => new URLSearchParams(window.location.search).get(name),
    () => null,
  );
}
