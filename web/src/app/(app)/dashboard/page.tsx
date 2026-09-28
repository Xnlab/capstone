"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, fmtDate, won } from "@/lib/api";
import type { Company, Contract } from "@/lib/types";
import { Card, Empty, FlowSteps, LinkButton, Loading, PageHeader } from "@/components/ui";

export default function Dashboard() {
  const [contracts, setContracts] = useState<Contract[] | null>(null);
  const [company, setCompany] = useState<Company | null>(null);

  useEffect(() => {
    api.get<Contract[]>("/contracts").then(setContracts);
    api.get<Company>("/company").then(setCompany);
  }, []);

  const companyIncomplete = company && (!company.company_name || !company.representative || !company.business_number);

  return (
    <>
      <PageHeader title="내 계약" desc="계약별로 필요한 서류를 모아 작성·검토합니다." action={<LinkButton href="/contracts/new">＋ 새 계약</LinkButton>} />

      {companyIncomplete && (
        <Card className="mb-5 flex flex-wrap items-center justify-between gap-3 border-amber-200 bg-amber-50 px-5 py-4">
          <div className="text-sm">
            <b>회사 정보가 비어 있습니다.</b> 한 번만 입력하면 모든 서류에 자동으로 채워집니다.
          </div>
          <LinkButton href="/company" variant="secondary">
            회사 정보 입력
          </LinkButton>
        </Card>
      )}

      <Card className="mb-6 px-5 py-4">
        <div className="mb-2 text-[13px] font-medium text-muted">서비스 흐름</div>
        <FlowSteps current={0} />
      </Card>

      {contracts === null ? (
        <Loading />
      ) : contracts.length === 0 ? (
        <Card>
          <Empty
            title="아직 등록된 계약이 없습니다"
            desc="계약명·발주처·금액·기간을 한 번 입력하면 착수계, 견적서, 보안서약서 등을 한꺼번에 만들 수 있습니다."
            action={<LinkButton href="/contracts/new">첫 계약 만들기</LinkButton>}
          />
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {contracts.map((c) => (
            <Link key={c.id} href={`/contracts/${c.id}`}>
              <Card className="h-full p-5 transition hover:border-primary/40 hover:shadow-sm">
                <div className="text-xs text-muted">{c.client_name || "발주처 미입력"}</div>
                <div className="mt-1 line-clamp-2 font-semibold">{c.contract_title}</div>
                <div className="mt-4 space-y-1 text-[13px] text-gray-600">
                  <div>금액 {c.amount ? won(c.amount) : "-"}</div>
                  <div>
                    기간 {fmtDate(c.start_date)} ~ {fmtDate(c.end_date)}
                  </div>
                </div>
                <div className="mt-4 border-t border-line pt-3 text-[13px]">
                  서류 <b className="text-primary">{c.document_count}</b>건
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
