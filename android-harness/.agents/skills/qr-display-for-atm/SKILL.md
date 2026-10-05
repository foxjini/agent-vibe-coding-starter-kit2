---
name: qr-display-for-atm
description: >-
  분석 결과의 session_id를 QR로 만들어 라즈베리파이 ATM 카메라가 읽을 수 있게
  화면에 띄울 때 사용하는 스킬. 모양보다 인식률이 우선이다.
---

# qr-display-for-atm

> **성공 기준 S4가 이 화면에서 갈린다.** 앱이 띄운 QR을 ATM이 못 읽으면
> 나머지가 다 되어도 이 앱은 제 역할을 못 한 것이다.

## 읽는 쪽 사정을 먼저 안다

라즈베리파이는 이렇게 읽는다.

- USB 웹캠을 **640×480**으로 연다
- **초당 10장**을 보면서 `cv2.QRCodeDetector`로 디코딩한다
- 한 장 처리에 약 12ms — 속도는 넉넉하다

즉 **속도가 아니라 화질이 문제다.** 휴대폰 화면이 어둡거나 QR이 작으면 못 읽는다.

## QR에 넣을 값

```json
{"session_id": "VP-000012"}
```

키는 `session_id` **하나만** 넣는다. 위험 상세나 개인정보를 넣지 않는다 —
ATM이 서버에서 직접 조회한다. 라즈베리파이는 이 값을 JSON으로 읽으므로
**공백이 있든 없든 상관없다** (아래 코드가 만드는 `{"session_id":"VP-000012"}`도
그대로 읽히는 것을 확인했다).

```kotlin
val payload = JSONObject().put("session_id", sessionId).toString()
```

## 만들기 (ZXing)

```gradle
implementation("com.google.zxing:core:3.5.3")
```

```kotlin
fun makeQr(payload: String, sizePx: Int): Bitmap {
    val hints = mapOf(
        EncodeHintType.CHARACTER_SET to "UTF-8",
        EncodeHintType.MARGIN to 2,                        // 여백(quiet zone)
        EncodeHintType.ERROR_CORRECTION to ErrorCorrectionLevel.M,
    )
    val matrix = QRCodeWriter().encode(
        payload, BarcodeFormat.QR_CODE, sizePx, sizePx, hints)

    val bmp = Bitmap.createBitmap(sizePx, sizePx, Bitmap.Config.RGB_565)
    for (x in 0 until sizePx) for (y in 0 until sizePx) {
        bmp.setPixel(x, y, if (matrix[x, y]) Color.BLACK else Color.WHITE)
    }
    return bmp
}
```

`MARGIN`을 0으로 두지 않는다. 여백이 없으면 디코더가 QR의 경계를 못 찾는다.

## 화면 — 네 가지를 지킨다

```kotlin
// 1. 화면이 꺼지지 않게
window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

// 2. 밝기를 최대로 (이 화면에서만)
window.attributes = window.attributes.apply { screenBrightness = 1.0f }
```

3. **배경은 흰색.** 테마 색이나 다크 모드가 QR 뒤로 들어오지 않게 한다
4. **QR을 화면 폭의 70% 이상**으로 크게

> **이 네 가지가 인식률의 거의 전부다.** 전시장 조명 아래에서 실패하는 1순위
> 원인은 휴대폰 화면이 어두운 것이다.

## 띄우는 조건

```kotlin
val showQr = risk_level != "SAFE" && session_id != null
```

`SAFE`일 때는 띄우지 않는다. 서버는 등급과 무관하게 `session_id`를 항상 만들지만,
**평범한 문자는 시스템이 건드리지 않는다**는 것이 이 작품의 원칙이다.

## 확인 (S4)

```
1. 보이스피싱 문자로 분석 → 위험 100점
2. QR 화면을 ATM 웹캠에 비춘다 (20~30cm)
3. 파이 데몬 로그에  QR 인식: {"session_id": "VP-0000xx"}  가 뜨는가
4. ATM 화면이 빨갛게 바뀌는가
5. 50만원을 눌러도 서보가 움직이지 않는가        ← 여기까지 되면 S4 통과
```

3번이 안 뜨면 **화면 밝기부터** 확인한다. 그다음이 거리, 그다음이 QR 크기다.

> **실측값을 기록해 둔다.** 잘 읽히는 거리와 각도를 재서 Flutter 담당 학생에게
> 넘긴다. 그 학생이 같은 시행착오를 반복하지 않아도 된다.
