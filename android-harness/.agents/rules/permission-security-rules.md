# 권한 · 보안 규칙

## 권한은 둘뿐이다

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.RECORD_AUDIO" />
```

**권한은 이게 전부다.** 더 요청하지 않는다.

## 권한은 아니지만 반드시 넣는 것 — `<queries>`

Android 11(API 30) 이상을 대상으로 하면, 음성 인식을 쓰는 앱은 매니페스트에
아래를 넣어야 한다 (공식 문서: *"apps that target Android 11 and interact with a
speech recognition service need to add the following `<queries>` element"*).
**권한 요청 화면은 뜨지 않는다** — 인식 서비스를 찾아도 된다는 선언일 뿐이다.

```xml
<queries>
    <intent>
        <action android:name="android.speech.RecognitionService" />
    </intent>
</queries>
```

빠뜨리면 받아쓰기가 **아무 오류 설명 없이** 동작하지 않는다.

| 요청하지 않는다 | 왜 |
|---|---|
| `READ_SMS` · `RECEIVE_SMS` | 공유 인텐트로 충분하다. 구글 플레이 정책 대상이기도 하다 |
| `WRITE_EXTERNAL_STORAGE` | 파일을 저장하지 않는다 |
| `READ_PHONE_STATE` · `CALL_LOG` | 통화를 건드리지 않는다 |

권한이 적을수록 시연에서 설명하기 쉽고, 심사에서도 유리하다.
**"개인정보를 통째로 읽지 않는다"는 것이 이 앱의 설명거리다.**

## RECORD_AUDIO 는 실행 중에 요청한다

API 23 이상은 설치 시점이 아니라 **쓰기 직전에** 요청해야 한다.
받아쓰기 버튼을 누른 순간 요청하고, 거부당하면 **왜 필요한지 설명하고
텍스트 직접 입력으로 계속 쓸 수 있게** 한다 (앱을 막지 않는다).

## 평문 HTTP

로컬망 시연이므로 평문 HTTP가 필요하다.

```xml
<application android:usesCleartextTraffic="true" ... >
```

**이건 시연용이라는 것을 기억한다.** 실제 배포 앱이라면 하지 않을 설정이다.

## 비밀값

- 시연 계정 비밀번호를 **코드에 박지 않는다** — 설정 화면에서 입력받는다
- 토큰을 로그에 전체 출력하지 않는다
- APK를 공개 저장소에 올리지 않는다
