---
name: share-intent-receiver
description: >-
  다른 앱(기본 문자 앱 등)에서 "공유"로 넘어온 텍스트를 받아 분석 입력란에 채울 때
  사용하는 스킬. READ_SMS 권한 없이 문자를 가져오는 방법이다.
---

# share-intent-receiver

> 이 방식을 쓰는 이유: **권한이 필요 없다.** 문자함을 통째로 읽지 않고,
> 사용자가 고른 한 건만 받는다. 시연에서 설명하기도 좋고 심사에서도 유리하다.

## 매니페스트

입력 화면 액티비티에 인텐트 필터를 더한다.

```xml
<activity android:name=".InputActivity" android:exported="true">
    <intent-filter>
        <action android:name="android.intent.action.MAIN" />
        <category android:name="android.intent.category.LAUNCHER" />
    </intent-filter>
    <intent-filter>
        <action android:name="android.intent.action.SEND" />
        <category android:name="android.intent.category.DEFAULT" />
        <data android:mimeType="text/plain" />
    </intent-filter>
</activity>
```

`android:exported="true"`가 없으면 API 31 이상에서 **앱이 설치조차 안 된다.**

## 받는 쪽

```kotlin
override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    setContentView(R.layout.activity_input)
    handleShared(intent)
}

// launchMode가 singleTop·singleTask면 이미 떠 있는 화면이 이쪽으로 공유를 받는다
override fun onNewIntent(intent: Intent) {
    super.onNewIntent(intent)
    setIntent(intent)
    handleShared(intent)
}

private fun handleShared(intent: Intent?) {
    // null 검사를 따로 둔다 — `intent?.action != …`만으로는 옛 컴파일러가
    // 아래 줄의 intent를 non-null로 보지 않아 컴파일 오류가 난다
    if (intent == null || intent.action != Intent.ACTION_SEND) return
    if (intent.type != "text/plain") return
    val shared = intent.getStringExtra(Intent.EXTRA_TEXT) ?: return
    inputField.setText(shared)
}
```

**두 곳 모두에서 받는다.** 어느 쪽으로 오는지는 액티비티의 `launchMode`에 달렸다.

| `launchMode` | 공유가 들어오면 |
|---|---|
| 기본값(`standard`) | 화면이 **새로 하나 더** 만들어진다 → `onCreate` |
| `singleTop` · `singleTask` | 떠 있는 화면이 그대로 받는다 → **`onNewIntent`** |

기본값으로 두면 공유할 때마다 입력 화면이 겹겹이 쌓인다(뒤로 가기를 여러 번
눌러야 빠져나온다). 거슬려서 `singleTask`로 바꾸는 순간 `onNewIntent`가 없으면
**"처음 한 번은 되는데 두 번째부터 안 된다"**는 증상이 나온다. 그래서 처음부터
두 곳 모두에서 받아 둔다.

## 받고 나서 바로 분석하지 않는다

입력란에 **채워만 두고 멈춘다.** 사용자가 내용을 확인하고 고칠 수 있어야 한다.

- 문자 앱이 보낸 텍스트에 발신번호·시각이 섞여 올 수 있다
- 어르신이 "이게 내가 보낸 그 문자가 맞나" 확인하는 순간이 시연에서 의미가 있다

## 앱 이름을 알아보기 쉽게

공유 목록에 뜨는 이름이 `app_name`이다. `MyApplication` 같은 기본값을 두지 말고
**"보이스피싱 검사"** 처럼 어르신이 목록에서 바로 찾을 이름으로 바꾼다.

## 확인 방법

```
문자 앱에서 메시지 길게 누르기 → 공유 → 목록에 우리 앱이 보이는가
→ 눌렀을 때 내용이 입력란에 채워져 있는가
→ 앱을 끄지 않고 다른 문자를 또 공유했을 때도 되는가   ← onNewIntent 확인
```

기기·기본 문자 앱에 따라 공유 메뉴 위치가 다르다. **시연에 쓸 실제 기기에서
한 번 확인해 둔다.**
