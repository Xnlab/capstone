"use client";

import type { StandardField, TemplateField } from "@/lib/types";
import { Badge } from "./ui";

const GROUP_LABEL: Record<string, string> = { company: "회사 정보", contract: "계약 정보", derived: "자동 계산", ai: "AI 작성" };

function confidenceBadge(f: TemplateField) {
  if (!f.field_key) return <Badge tone="red">연결 안 됨</Badge>;
  if (f.method === "user") return <Badge tone="indigo">직접 지정</Badge>;
  const pct = Math.round(f.confidence * 100);
  const tone = f.confidence >= 0.9 ? "green" : f.confidence >= 0.7 ? "amber" : "red";
  return (
    <Badge tone={tone}>
      {f.method === "ai" ? "AI" : "사전"} {pct}%
    </Badge>
  );
}

/** 양식 항목명 ↔ 내부 표준 데이터 연결 편집기 (3주차 "AI 의미 분석" 결과 확인) */
export default function MappingEditor({
  fields,
  standard,
  onChange,
}: {
  fields: TemplateField[];
  standard: StandardField[];
  onChange: (fields: TemplateField[]) => void;
}) {
  const groups = Object.entries(GROUP_LABEL).map(([g, label]) => ({ label, items: standard.filter((s) => s.group === g) }));

  const set = (i: number, key: string) => {
    const next = fields.map((f, k) => (k === i ? { ...f, field_key: key || null, method: "user" as const, confidence: key ? 1 : 0 } : f));
    onChange(next);
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs text-muted">
            <th className="px-5 py-2.5 font-medium">양식의 항목명</th>
            <th className="px-2 py-2.5 font-medium">위치</th>
            <th className="px-2 py-2.5 font-medium">→ 내부 표준 데이터</th>
            <th className="px-5 py-2.5 font-medium">판단</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {fields.map((f, i) => {
            const ctx = f.context.replace(/[\s|]+$/, "");
            return (
              <tr key={i} className={!f.field_key ? "bg-red-50/40" : ""}>
                <td className="px-5 py-2.5">
                  <div className="font-medium">{f.label}</div>
                  {ctx && ctx !== f.label && <div className="max-w-[260px] truncate text-xs text-muted">{ctx}</div>}
                </td>
                <td className="px-2 py-2.5 text-xs text-muted">{f.location.type === "cell" ? "표 칸" : f.location.type === "para" ? "문단" : "PDF 줄"}</td>
                <td className="px-2 py-2.5">
                  <select
                    value={f.field_key ?? ""}
                    onChange={(e) => set(i, e.target.value)}
                    className="h-9 w-full rounded-lg border border-line bg-white px-2 text-sm outline-none focus:border-primary"
                  >
                    <option value="">(연결 안 함 · 빈칸으로 둠)</option>
                    {groups.map((g) => (
                      <optgroup key={g.label} label={g.label}>
                        {g.items.map((s) => (
                          <option key={s.key} value={s.key}>
                            {s.label} ({s.key})
                          </option>
                        ))}
                      </optgroup>
                    ))}
                  </select>
                </td>
                <td className="px-5 py-2.5">{confidenceBadge(f)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
