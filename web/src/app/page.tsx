import Link from "next/link";

const STEPS = [
  { n: "01", t: "서류 요청", d: "“착수계 제출해 주세요” — 요청받은 서류를 검색하거나 기업 양식을 올립니다." },
  { n: "02", t: "AI 분석", d: "양식의 항목명·위치·문맥을 분석해 ‘총 용역대금’도 ‘계약금액’으로 이해합니다." },
  { n: "03", t: "자동 작성", d: "한 번 저장한 회사정보와 계약정보가 모든 서류에 자동으로 채워집니다." },
  { n: "04", t: "검토·다운로드", d: "누락·금액 오류·서류 간 불일치를 검토한 뒤 Word/PDF로 받거나 메일로 보냅니다." },
];

const PAINS = ["양식 찾기부터 업무", "같은 정보 반복 입력", "서류마다 다른 금액·기간", "제출 전 누락 확인"];

export default function Landing() {
  return (
    <div className="min-h-screen bg-white">
      <header className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <div className="flex items-center gap-2 font-semibold">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-sm font-bold text-white">AI</span>
          AI 계약·행정서류 자동화
        </div>
        <div className="flex gap-2 text-sm">
          <Link href="/login" className="rounded-lg px-4 py-2 text-gray-600 hover:bg-gray-50">
            로그인
          </Link>
          <Link href="/register" className="rounded-lg bg-primary px-4 py-2 font-medium text-white hover:bg-indigo-700">
            시작하기
          </Link>
        </div>
      </header>

      <section className="mx-auto max-w-6xl px-6 pb-16 pt-16 sm:pt-24">
        <p className="mb-4 text-sm font-semibold text-primary">스타트업·소규모 사업자를 위한 계약 행정업무 자동화</p>
        <h1 className="max-w-3xl text-4xl font-bold leading-tight tracking-tight sm:text-5xl">
          서류를 작성하는 것보다
          <br />
          양식을 찾는 게 더 오래 걸렸다면.
        </h1>
        <p className="mt-6 max-w-2xl text-lg text-gray-600">
          요청받은 계약·행정서류를 찾고, 회사·계약정보로 자동 작성하고, 제출 전 오류까지 검토합니다. 기업마다 다른 자체 양식도 AI가 이해합니다.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/register" className="rounded-lg bg-primary px-6 py-3 font-medium text-white hover:bg-indigo-700">
            무료로 시작하기
          </Link>
          <Link href="/login" className="rounded-lg border border-line px-6 py-3 font-medium hover:bg-gray-50">
            로그인
          </Link>
        </div>
        <div className="mt-10 flex flex-wrap gap-2">
          {PAINS.map((p) => (
            <span key={p} className="rounded-full bg-gray-100 px-3 py-1 text-sm text-gray-600">
              {p}
            </span>
          ))}
        </div>
      </section>

      <section className="border-t border-line bg-background">
        <div className="mx-auto grid max-w-6xl gap-4 px-6 py-16 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s) => (
            <div key={s.n} className="rounded-xl border border-line bg-white p-5">
              <div className="text-sm font-bold text-primary">{s.n}</div>
              <div className="mt-2 font-semibold">{s.t}</div>
              <p className="mt-2 text-sm leading-relaxed text-gray-600">{s.d}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="py-8 text-center text-xs text-muted">CAPSTONE DESIGN · 구예찬 · 원정연 · 정한솔</footer>
    </div>
  );
}
