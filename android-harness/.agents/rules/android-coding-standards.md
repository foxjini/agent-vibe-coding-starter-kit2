# 안드로이드 코딩 표준

## 크기

- **Activity 3~4개, 파일 10개 안쪽으로 끝낸다.** 넘어가면 과하게 만들고 있는 것이다
- 한 파일 200줄을 넘으면 정말 필요한지 다시 본다

## 쓰지 않는 것

| 쓰지 않는다 | 대신 |
|---|---|
| Jetpack Compose | View + XML 레이아웃 |
| MVVM · Clean Architecture | Activity 안에서 직접 |
| Retrofit · Hilt · Room · Coroutine Flow | `HttpURLConnection` + 백그라운드 스레드 |
| DataBinding · ViewBinding 생성기 | `findViewById` |

> 목적은 **빨리 확인하고 버리는 것**이다. 구조를 갖추는 시간이 확인하는 시간보다
> 길어지면 이 앱은 실패한 것이다. Flutter 앱에서 제대로 갖추면 된다.

## 네트워크

- 메인 스레드에서 네트워크를 호출하지 않는다 (`NetworkOnMainThreadException`)
- 백그라운드 스레드 → `runOnUiThread`로 화면 갱신. 그 이상 필요 없다
- 타임아웃은 연결 5초 / 읽기 10초

## 문자열

- **사용자에게 보이는 문구는 한국어**로 쓴다
- 어르신이 보는 화면이므로 본문 **18sp 이상**
- 오류 문구는 "무엇이 잘못됐고 무엇을 하면 되는지"를 함께 적는다.
  `Exception: null` 같은 것을 그대로 띄우지 않는다

## 설정값

- 서버 주소·계정은 `SharedPreferences`에 저장한다
- **코드에 박지 않는다.** 전시장에서 IP가 바뀔 때마다 APK를 다시 빌드하게 된다

## 로그

- `Log.d(TAG, ...)`로 **요청 URL과 응답 코드**는 반드시 남긴다.
  전시장에서 무엇이 막혔는지 이것만 봐도 절반은 알 수 있다
- 토큰 전체를 로그에 남기지 않는다 (앞 10자까지만)
