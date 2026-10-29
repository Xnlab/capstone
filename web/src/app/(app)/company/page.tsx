"use client";

import { useEffect, useState, type FormEvent } from "react";
import { api } from "@/lib/api";
import { useQueryParam } from "@/lib/hooks";
import type { Company } from "@/lib/types";
import { Button, Card, CardHeader, ErrorText, Field, Input, Loading, PageHeader } from "@/components/ui";

const FIELDS: { key: Exclude<keyof Company, "seal_image" | "seal_size_mm" | "has_seal">; label: string; placeholder: string; required?: boolean; hint?: string }[] = [
  { key: "company_name", label: "회사명(상호)", placeholder: "(주)마코", required: true },
  { key: "representative", label: "대표자명", placeholder: "홍길동", required: true },
  { key: "business_number", label: "사업자등록번호", placeholder: "123-45-67890", required: true, hint: "000-00-00000 형식" },
  { key: "address", label: "사업장 주소", placeholder: "대전광역시 유성구 …" },
  { key: "phone", label: "대표 연락처", placeholder: "042-000-0000" },
  { key: "email", label: "대표 이메일", placeholder: "contact@company.com" },
  { key: "manager_name", label: "실무 담당자", placeholder: "김담당", hint: "사업책임자·현장대리인 칸에 사용" },
  { key: "business_type", label: "업태", placeholder: "정보통신업", hint: "견적서 공급자 정보에 사용" },
  { key: "business_item", label: "종목", placeholder: "소프트웨어 개발", hint: "견적서 공급자 정보에 사용" },
  { key: "bank_name", label: "거래은행", placeholder: "○○은행", hint: "선금·대금 지급 서류에 사용" },
  { key: "account_number", label: "계좌번호", placeholder: "000-000-000000", hint: "선금·대금 지급 서류에 사용" },
  { key: "account_holder", label: "예금주", placeholder: "(주)회사명", hint: "선금·대금 지급 서류에 사용" },
];

export default function CompanyPage() {
  const [form, setForm] = useState<Company | null>(null);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [sealBusy, setSealBusy] = useState(false);
  const [sealError, setSealError] = useState("");
  const [sealSize, setSealSize] = useState(20);
  const welcome = useQueryParam("welcome") !== null;

  useEffect(() => {
    api.get<Company>("/company").then((company) => {
      setForm(company);
      setSealSize(company.seal_size_mm);
    });
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!form) return;
    setLoading(true);
    setError("");
    try {
      setForm(await api.put<Company>("/company", form));
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const updateSeal = async (action: () => Promise<Company>) => {
    setSealBusy(true);
    setSealError("");
    try {
      const company = await action();
      setForm((previous) => previous && { ...previous, seal_image: company.seal_image, has_seal: company.has_seal, seal_size_mm: company.seal_size_mm });
      setSealSize(company.seal_size_mm);
    } catch (err) {
      setSealError((err as Error).message);
    } finally {
      setSealBusy(false);
    }
  };

  if (!form) return <Loading />;

  return (
    <>
      <PageHeader title="회사 정보" desc="한 번 입력하면 모든 서류의 업체·담당자·계좌 정보에 자동으로 채워집니다." />
      {welcome && (
        <Card className="mb-5 border-primary/30 bg-primary-soft px-5 py-4 text-sm">
          가입을 환영합니다! 먼저 회사 정보를 입력해 주세요. 이후 계약을 만들면 서류가 자동으로 작성됩니다.
        </Card>
      )}
      <form onSubmit={submit}>
        <Card>
          <CardHeader title="기본 정보" desc="개인정보 최소 수집 — 서류 작성에 꼭 필요한 항목만 저장합니다." />
          <div className="grid gap-4 p-5 sm:grid-cols-2">
            {FIELDS.map((f) => (
              <Field key={f.key} label={f.label} required={f.required} hint={f.hint}>
                <Input value={form[f.key]} placeholder={f.placeholder} onChange={(e) => setForm({ ...form, [f.key]: e.target.value })} />
              </Field>
            ))}
          </div>
          <div className="flex items-center justify-end gap-3 border-t border-line px-5 py-4">
            <ErrorText>{error}</ErrorText>
            {saved && <span className="text-sm text-emerald-600">저장되었습니다 ✓</span>}
            <Button type="submit" loading={loading}>
              저장
            </Button>
          </div>
        </Card>
      </form>
      <Card className="mt-5">
        <CardHeader title="회사 도장" desc="일반 미리보기에는 인감을 넣지 않습니다. 인감 관리와 인감 포함 출력·발송에는 작업별 비밀번호 확인이 필요합니다." />
        <div className="grid gap-6 p-5 sm:grid-cols-[1fr_260px]">
          <div className="space-y-4">
            <Field label="도장 이미지" hint="PNG·JPEG, 최대 3MB. 여백이 적은 투명 PNG를 권장합니다.">
              <Input type="file" accept="image/png,image/jpeg" disabled={sealBusy} onChange={(e) => {
                const file = e.target.files?.[0];
                e.target.value = "";
                if (file) void updateSeal(() => api.upload<Company>("/company/seal", file));
              }} />
            </Field>
            <Field label="도장 크기" hint="가장 긴 변 기준 10~30mm. 원본 비율은 유지됩니다.">
              <div className="flex items-center gap-3">
                <Input type="number" min={10} max={30} step={1} value={sealSize} disabled={sealBusy} className="max-w-24" onChange={(e) => setSealSize(Number(e.target.value))} />
                <span className="text-sm text-muted">mm</span>
                <Button variant="secondary" disabled={!form.has_seal || sealBusy || !Number.isFinite(sealSize) || sealSize < 10 || sealSize > 30} onClick={() => updateSeal(() => api.put<Company>("/company/seal", { size_mm: sealSize }))}>크기 저장</Button>
              </div>
            </Field>
            {form.has_seal && <Button variant="secondary" disabled={sealBusy} onClick={() => updateSeal(() => api.del<Company>("/company/seal"))}>도장 등록 해제</Button>}
            {sealBusy && <p className="text-sm text-muted" role="status">도장을 저장하고 있습니다…</p>}
            <ErrorText>{sealError}</ErrorText>
          </div>
          <div className="rounded-lg border border-line bg-slate-50 p-4">
            <div className="mb-4 text-xs text-muted">인감은 기본적으로 숨겨집니다.</div>
            {form.has_seal && !form.seal_image && <Button variant="secondary" onClick={async () => {
              try { const result = await api.get<{ seal_image: string }>("/company/seal"); setForm({ ...form, seal_image: result.seal_image }); }
              catch (e) { setSealError((e as Error).message); }
            }}>비밀번호 확인 후 인감 보기</Button>}
            {form.seal_image && <Button variant="secondary" onClick={() => setForm({ ...form, seal_image: "" })}>인감 숨기기</Button>}
            <div className="flex min-h-32 items-center justify-end gap-3 rounded bg-white px-3">
              <span className="text-sm">대표자 : {form.representative || "대표자명"}</span>
              <span className="relative flex shrink-0 items-center justify-center" style={{ width: `${Math.min(30, Math.max(10, sealSize || 20))}mm`, height: `${Math.min(30, Math.max(10, sealSize || 20))}mm` }}>
                {form.seal_image && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={form.seal_image} alt="등록한 회사 도장" className="absolute inset-0 h-full w-full object-contain" />
                )}
                <span className="relative z-10 text-sm">(인)</span>
              </span>
            </div>
            <p className="mt-3 text-xs text-muted">도장은 글자 뒤에 겹쳐 표시됩니다.</p>
          </div>
        </div>
      </Card>
    </>
  );
}
