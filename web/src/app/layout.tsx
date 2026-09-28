import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI 계약·행정서류 자동화",
  description: "요청받은 계약·행정서류를 찾고, 자동으로 작성하고, 검토까지 한 번에",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ko" className="h-full antialiased">
      <head>
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
        />
      </head>
      <body className="min-h-full">{children}</body>
    </html>
  );
}
