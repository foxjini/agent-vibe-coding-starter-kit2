"use client";

import React, { useEffect, useState } from "react";
import QRCode from "qrcode";

interface QrCodeProps {
  value: string;
  size?: number;
  /** 대비를 위해 QR 은 항상 흰 바탕에 검정으로 그린다 (어두운 화면에서도) */
  className?: string;
}

/**
 * QR 코드 그림
 *
 * 부스 대형 화면에 띄워 관람객이 폰으로 찍는다. 어두운 무대 팔레트 위에서도
 * 인식되도록 QR 자체는 흰 바탕·검정으로 고정한다 — 색을 맞추려다 대비가
 * 떨어지면 카메라가 못 읽는다.
 */
export function QrCode({ value, size = 168, className = "" }: QrCodeProps) {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    QRCode.toDataURL(value, {
      margin: 1,
      width: size * 2, // 고해상도 화면에서 흐려지지 않게 2배로 그린다
      errorCorrectionLevel: "M",
      color: { dark: "#101014", light: "#FFFFFF" },
    })
      .then((url) => {
        if (alive) setSrc(url);
      })
      .catch(() => {
        /* QR 을 못 그려도 화면 전체가 멈추면 안 된다 */
      });
    return () => {
      alive = false;
    };
  }, [value, size]);

  return (
    <span
      className={`inline-block rounded-xl bg-white p-2 ${className}`}
      style={{ width: size + 16, height: size + 16 }}
    >
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element -- data URL이라 최적화 대상이 아니다
        <img src={src} alt="체험권 발급 QR 코드" width={size} height={size} />
      ) : (
        <span className="block w-full h-full rounded-lg bg-neutral-200" aria-hidden />
      )}
    </span>
  );
}
