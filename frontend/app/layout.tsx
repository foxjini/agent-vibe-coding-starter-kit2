import type { Metadata, Viewport } from "next";
import { Geist_Mono } from "next/font/google";
import "./globals.css";

/* 숫자·코드 전용. 본문 한글은 Pretendard(globals.css)가 맡는다. */
const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "학교 노래방 부스",
    template: "%s · 학교 노래방 부스",
  },
  description:
    "웹으로 예약하고 일회성 비밀번호로 입장하는 학교 노래방 부스 예약·운영 시스템",
  applicationName: "학교 노래방 부스",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#F1F3F1",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ko" className={`${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
