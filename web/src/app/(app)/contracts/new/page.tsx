"use client";

import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Contract } from "@/lib/types";
import ContractForm, { emptyContract } from "@/components/ContractForm";
import { Card, PageHeader } from "@/components/ui";

export default function NewContractPage() {
  const router = useRouter();
  return (
    <>
      <PageHeader title="새 계약" desc="계약 기본정보를 한 번 입력하면, 이후 추가하는 모든 서류에 자동으로 반영됩니다." back={{ href: "/dashboard", label: "내 계약" }} />
      <Card className="max-w-2xl p-5">
        <ContractForm
          initial={emptyContract}
          submitLabel="계약 만들고 서류 추가하기 →"
          onSubmit={async (v) => {
            const c = await api.post<Contract>("/contracts", v);
            router.push(`/contracts/${c.id}`);
          }}
        />
      </Card>
    </>
  );
}
