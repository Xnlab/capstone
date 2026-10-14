"use client";

import { useEffect, useState, type FormEvent } from "react";
import { api } from "@/lib/api";
import { useQueryParam } from "@/lib/hooks";
import type { Company } from "@/lib/types";
import { Button, Card, CardHeader, ErrorText, Field, Input, Loading, PageHeader } from "@/components/ui";

const FIELDS: { key: keyof Company; label: string; placeholder: string; required?: boolean; hint?: string }[] = [
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
  const welcome = useQueryParam("welcome") !== null;

  useEffect(() => {
    api.get<Company>("/company").then(setForm);
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
    </>
  );
}
