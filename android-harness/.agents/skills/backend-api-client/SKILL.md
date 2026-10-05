---
name: backend-api-client
description: >-
  안드로이드 앱에서 스마트 금융 보안 ATM 백엔드(FastAPI)에 로그인하고 문자·통화
  텍스트 분석을 요청할 때 사용하는 스킬. 응답 봉투({"data"}/{"error"}) 처리와
  오류 코드별 대응을 포함한다.
---

# backend-api-client

> 계약 자체는 `.agents/rules/api-contract-rules.md`에 있다. 이 스킬은 **그것을
> 안드로이드에서 어떻게 부르는가**를 다룬다.

## 라이브러리를 더하지 않는다

`HttpURLConnection` 하나로 끝난다. Retrofit을 쓰면 인터페이스·컨버터·DI까지
따라오는데, 부를 API가 **세 개뿐**이라 얻는 것이 없다.

## 응답 봉투를 한 곳에서 벗긴다

| | 모양 |
|---|---|
| 성공 | `{"data": ...}` |
| 실패 | `{"error": {"code": "...", "message": "..."}}` (형식 오류면 `details` 목록이 더 붙는다) |

**`detail`이 아니라 `error`다.** FastAPI 기본값은 `detail`이지만, 이 백엔드는
`backend/main.py`의 처리기가 전부 `error`로 바꿔서 보낸다. 서버를 띄워 직접
확인한 값이다. `detail`을 찾으면 **모든 오류 메시지를 놓친다.**

```kotlin
class ApiException(val code: String, override val message: String) : Exception(message)

/** GET·POST가 함께 쓰는 한 곳. 봉투를 벗기고 실패는 ApiException으로 바꾼다. */
private fun request(method: String, path: String, body: JSONObject?, token: String?): JSONObject {
    val conn = (URL(baseUrl.trimEnd('/') + path).openConnection() as HttpURLConnection).apply {
        requestMethod = method
        connectTimeout = 5_000
        readTimeout = 10_000
        setRequestProperty("Accept", "application/json")
        token?.let { setRequestProperty("Authorization", "Bearer $it") }
        if (body != null) {
            doOutput = true
            setRequestProperty("Content-Type", "application/json; charset=utf-8")
        }
    }
    try {
        body?.let { b -> conn.outputStream.use { it.write(b.toString().toByteArray(Charsets.UTF_8)) } }

        val status = conn.responseCode
        Log.d(TAG, "$method $path -> $status")
        val ok = status in 200..299
        // 4xx/5xx인데 본문이 없으면 errorStream이 null이다
        val stream = if (ok) conn.inputStream else conn.errorStream
        val text = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()

        // 프록시·공유기가 HTML 오류 페이지를 돌려줄 수도 있다 — JSON이 아니면 여기서 멈춘다
        val json = runCatching { JSONObject(text) }.getOrElse {
            throw ApiException("HTTP_$status", "서버 응답을 읽을 수 없습니다 (HTTP $status)")
        }
        if (ok) return json.getJSONObject("data")

        val error = json.optJSONObject("error")
        throw ApiException(
            error?.optString("code")?.takeIf { it.isNotEmpty() } ?: "HTTP_$status",
            error?.optString("message")?.takeIf { it.isNotEmpty() } ?: "서버가 요청을 거부했습니다 (HTTP $status)",
        )
    } finally {
        conn.disconnect()
    }
}

private fun get(path: String, token: String? = null) = request("GET", path, null, token)
private fun post(path: String, body: JSONObject, token: String? = null) = request("POST", path, body, token)
```

**`charset=utf-8`을 빠뜨리지 않는다.** 한글 본문이 깨져서 키워드가 안 걸리면
"분석 엔진이 이상하다"고 엉뚱한 곳을 뒤지게 된다.

## 세 번의 호출

```kotlin
// 1. 연결 확인 — /api/v1 접두사가 없다
fun health(): Boolean = get("/health").optString("status") == "ok"

// 2. 로그인
fun login(id: String, pw: String): String =
    post("/api/v1/auth/login", JSONObject().put("username", id).put("password", pw))
        .getString("access_token")

// 3. 분석
fun analyze(text: String, token: String): JSONObject =
    post("/api/v1/analysis", JSONObject().put("message", text), token)
```

## 보내기 전에 길이를 확인한다

```kotlin
if (text.isBlank()) { /* "검사할 내용을 입력해 주세요" */ }
if (text.length > 2000) { /* 사용자에게 알리고 줄이게 한다 */ }
```

서버가 거절하기 전에 앱에서 막는 편이 친절하다. 입력 화면에
`1,432 / 2,000` 처럼 항상 보여 준다.

## 오류는 서버 문구를 그대로 띄운다

서버는 `error.message`에 **사용자용 한국어 문구**를 담아 보낸다
(예: "로그인이 만료되었습니다. 다시 로그인해 주세요."). 앱이 코드마다 문구를
새로 지어낼 필요가 없다. **행동이 필요한 코드만** 따로 처리한다.

| `error.code` | 언제 | 앱이 할 일 |
|---|---|---|
| `UNAUTHORIZED` | 토큰 없이 요청 | **설정 화면으로 보내 다시 로그인** |
| `TOKEN_EXPIRED` | 12시간이 지남 | 〃 |
| `INVALID_TOKEN` | 토큰 손상 | 〃 |
| `USER_NOT_FOUND` | 서버 DB를 새로 만든 뒤 옛 토큰 | 〃 |
| `INVALID_CREDENTIALS` | 비밀번호 틀림 | `message`를 띄운다 |
| `MESSAGE_REQUIRED` | 빈 텍스트 | `message`를 띄운다 |
| `VALIDATION_ERROR` | 2000자 초과 등 | `message`를 띄운다 |

```kotlin
private val RELOGIN = setOf("UNAUTHORIZED", "TOKEN_EXPIRED", "INVALID_TOKEN", "USER_NOT_FOUND")

fun showError(e: Exception) = when {
    e is ApiException && e.code in RELOGIN -> goToSettings(e.message)
    e is ApiException -> toast(e.message)
    // 연결 자체가 안 될 때 — 전시장에서 가장 흔하다. 현재 주소를 꼭 함께 보여 준다
    e is IOException -> toast("서버에 연결할 수 없습니다 — $baseUrl")
    else -> toast("처리하지 못했습니다: ${e.javaClass.simpleName}")
}
```

**연결 실패 문구에 현재 서버 주소를 함께 띄우는 것이 규칙이다.** 전시장에서
가장 흔한 실패는 서버 주소가 바뀐 것이고, 주소가 화면에 보이면 바로 안다.

## 스레드

```kotlin
Thread {
    try {
        val data = api.analyze(text, token)
        runOnUiThread { showResult(data) }
    } catch (e: Exception) {
        runOnUiThread { showError(e) }
    }
}.start()
```

이 앱에는 이걸로 충분하다. 코루틴·Flow를 도입하지 않는다.
