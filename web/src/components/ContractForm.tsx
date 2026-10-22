"use client";

import { useEffect, useId, useState, type FormEvent } from "react";
import { api } from "@/lib/api";
import type { Contract } from "@/lib/types";
import { Button, ErrorText, Field, Input, Textarea } from "./ui";

export type ContractInput = Pick<Contract, "contract_title" | "client_name" | "amount" | "contract_date" | "start_date" | "end_date" | "description">;

export const emptyContract: ContractInput = { contract_title: "", client_name: "", amount: 0, contract_date: null, start_date: null, end_date: null, description: "" };

export default function ContractForm({
  initial,
  submitLabel,
  onSubmit,
}: {
  initial: ContractInput;
  submitLabel: string;
  onSubmit: (v: ContractInput) => Promise<void>;
}) {
  const [v, setV] = useState<ContractInput>(initial);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [organizations, setOrganizations] = useState<string[]>([]);
  const organizationList = useId();
  useEffect(() => { api.get<string[]>("/templates/organizations").then(setOrganizations).catch(() => setOrganizations([])); }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (v.start_date && v.end_date && v.start_date > v.end_date) {
      setError("착수일이 완료일보다 늦을 수 없습니다.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      await onSubmit(v);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <Field label="계약명" required>
        <Input required value={v.contract_title} onChange={(e) => setV({ ...v, contract_title: e.target.value })} placeholder="2026 스마트관광 앱 고도화 용역" />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="발주처" hint="서류의 '귀하'·'수신' 칸에 들어갑니다">
          <Input list={organizationList} autoComplete="off" value={v.client_name} onChange={(e) => setV({ ...v, client_name: e.target.value })} placeholder="기관·기업명을 입력하거나 선택하세요" />
          <datalist id={organizationList}>{organizations.map(name => <option value={name} key={name} />)}</datalist>
        </Field>
        <Field label="계약금액 (부가세 포함, 원)" hint={v.amount ? `공급가액 ${Math.round(v.amount / 1.1).toLocaleString()}원 + 부가세 ${(v.amount - Math.round(v.amount / 1.1)).toLocaleString()}원` : undefined}>
          <Input
            inputMode="numeric"
            value={v.amount ? v.amount.toLocaleString("ko-KR") : ""}
            onChange={(e) => setV({ ...v, amount: Number(e.target.value.replace(/[^\d]/g, "")) || 0 })}
            placeholder="55,000,000"
          />
        </Field>
        <div className="sm:col-span-2">
          <Field label="계약일자" hint="계약을 체결한 날짜입니다. 착수계·완료계 등에 자동 입력됩니다.">
            <Input type="date" value={v.contract_date ?? ""} onChange={(e) => setV({ ...v, contract_date: e.target.value || null })} />
          </Field>
        </div>
        <Field label="착수일">
          <Input type="date" value={v.start_date ?? ""} onChange={(e) => setV({ ...v, start_date: e.target.value || null })} />
        </Field>
        <Field label="완료일">
          <Input type="date" value={v.end_date ?? ""} onChange={(e) => setV({ ...v, end_date: e.target.value || null })} />
        </Field>
      </div>
      <Field label="업무내용" hint="과업수행계획서의 '과업 내용'과 AI 과업 개요 문장 생성에 사용됩니다">
        <Textarea rows={3} value={v.description} onChange={(e) => setV({ ...v, description: e.target.value })} placeholder="관광 앱 신규 기능 개발 및 운영 유지보수" />
      </Field>
      <ErrorText>{error}</ErrorText>
      <div className="flex justify-end">
        <Button type="submit" loading={loading}>
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}
