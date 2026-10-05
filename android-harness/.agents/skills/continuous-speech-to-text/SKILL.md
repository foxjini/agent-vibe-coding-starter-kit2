---
name: continuous-speech-to-text
description: >-
  다른 기기에서 나오는 통화 음성(녹음 재생 또는 옆 폰의 스피커폰)을 실시간으로
  받아써서 텍스트로 쌓을 때 사용하는 스킬. 안드로이드 SpeechRecognizer가 스스로
  멈추는 문제를 재시작으로 해결하는 방법과, 같은 폰의 통화는 받아쓸 수 없다는
  제약을 다룬다.
---

# continuous-speech-to-text

> **이 앱에서 가장 까다로운 부분이다.** 나머지는 API를 부르고 화면에 그리는
> 일이지만, 여기는 안드로이드 플랫폼의 규칙과 싸워야 한다.

## 먼저 — 같은 폰의 통화는 받아쓸 수 없다

**통화가 걸려 있는 동안 일반 앱이 마이크로 받는 소리는 무음이다.** 스피커폰으로
바꿔도 같다. 안드로이드 공식 문서("Sharing audio input")의 규칙이다.

> *A voice call is active if the audio mode returned by `AudioManager.getMode()`
> is `MODE_IN_CALL` or `MODE_IN_COMMUNICATION`. … The call always receives audio.
> The app can capture audio if it is an accessibility service.*

예외는 접근성 서비스와 제조사 기본 앱뿐이다. 접근성 서비스는 장애가 있는 사용자를
돕기 위한 기능이므로 이 용도로 쓰지 않는다.

**그래서 통화와 받아쓰기를 서로 다른 기기로 나눈다.**

| 구성 | 통화 소리를 내는 쪽 | 받아쓰는 쪽 | 언제 |
|---|---|---|---|
| **녹음 재생 (기본)** | 노트북·다른 폰·스피커로 녹음된 대본 재생 | 앱이 깔린 폰 | **전시 기본.** 대본·볼륨을 통제할 수 있어 가장 안정적 |
| 두 대 실시간 | 폰 ①에서 통화 + 스피커폰 | 옆에 둔 폰 ② (앱) | 실감이 필요할 때 |

> 받아쓰기가 처음부터 아무것도 안 잡으면 **그 폰에 통화가 걸려 있는지**부터 본다.
> 오류도 안 나고 조용히 무음만 들어오므로 원인을 찾기 어렵다.

## 매니페스트 — 빠뜨리면 아무 설명 없이 안 된다

Android 11(API 30) 이상을 대상으로 하면 아래가 **반드시** 필요하다. 권한이 아니라
"음성 인식 서비스를 찾아도 된다"는 선언이다. 없으면 기기에 인식 서비스가 있어도
앱 눈에 보이지 않는다.

```xml
<manifest ...>
    <uses-permission android:name="android.permission.RECORD_AUDIO" />

    <queries>
        <intent>
            <action android:name="android.speech.RecognitionService" />
        </intent>
    </queries>
    ...
</manifest>
```

## 핵심 문제 — 스스로 멈춘다

`SpeechRecognizer`는 **한 문장을 받아쓰고 끝내도록** 만들어졌다. 검색어를 말하는
용도를 가정한 API다. 그래서 말이 잠깐 끊기면 `onResults` 또는 `onError`를 부르고
**멈춘다.**

통화는 말과 말 사이가 계속 끊긴다. 그대로 두면 **첫 문장만 받아쓰고 끝난다.**

→ 그래서 **끝날 때마다 다시 시작**한다. 단, **다시 시작해도 소용없는 오류**
(권한 없음, 한국어 미지원)에서는 멈추고 이유를 알린다. 안 그러면 화면에는
아무 변화 없이 뒤에서 끝없이 헛돈다.

## 구현

`SpeechRecognizer`의 메서드는 **메인 스레드에서만** 부른다(공식 규칙).
아래 코드는 화면에서 부르고, 재시작도 메인 루퍼의 `Handler`로 한다.

```kotlin
class CallDictation(
    private val context: Context,
    private val onText: (String) -> Unit,       // 인식된 문장을 이어 붙일 곳
    private val onStopped: (String) -> Unit,    // 더 못 하게 됐을 때 이유를 알릴 곳
) : RecognitionListener {

    private var recognizer: SpeechRecognizer? = null
    private var listening = false               // 사용자가 [중지]를 눌렀는가
    private var failures = 0                    // 연속 실패 횟수 (결과가 오면 0)
    private val handler = Handler(Looper.getMainLooper())

    private fun intent() = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
        putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                 RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
        putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ko-KR")
        putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)   // 말하는 도중에도 보인다
    }

    fun start() {
        // 인식 서비스가 없는 기기도 있다. <queries>를 빠뜨려도 여기서 false가 나온다
        if (!SpeechRecognizer.isRecognitionAvailable(context)) {
            onStopped("이 기기에서는 음성 인식을 쓸 수 없습니다. 텍스트를 직접 입력해 주세요.")
            return
        }
        listening = true
        failures = 0
        recognizer = SpeechRecognizer.createSpeechRecognizer(context).also {
            it.setRecognitionListener(this)
            it.startListening(intent())
        }
    }

    fun stop() {
        listening = false                       // 반드시 먼저 — 아니면 onError가 되살린다
        handler.removeCallbacksAndMessages(null)
        recognizer?.destroy()
        recognizer = null
    }

    /** 끝났으면 다시 시작한다. 곧바로 부르면 ERROR_RECOGNIZER_BUSY가 난다. */
    private fun restart(delayMs: Long = 300) {
        if (!listening) return
        handler.postDelayed({
            if (!listening) return@postDelayed
            recognizer?.cancel()
            recognizer?.startListening(intent())
        }, delayMs)
    }

    override fun onResults(results: Bundle) {
        failures = 0
        results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
            ?.firstOrNull()
            ?.takeIf { it.isNotBlank() }
            ?.let { onText(it) }
        restart()                               // ← 이 줄이 없으면 첫 문장에서 끝난다
    }

    override fun onError(error: Int) {
        when (error) {
            // 말이 없어서 난 오류 — 통화 중 침묵일 뿐 정상이다
            SpeechRecognizer.ERROR_NO_MATCH,
            SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> restart()

            // 앞 세션이 아직 안 끝났다 — 조금 더 기다렸다가
            SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> restart(800)

            // 다시 해도 소용없는 오류 — 멈추고 알린다
            SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> {
                stop(); onStopped("마이크 권한이 필요합니다.")
            }
            12, 13 -> {                         // ERROR_LANGUAGE_NOT_SUPPORTED / _UNAVAILABLE (API 31+)
                stop(); onStopped("이 기기의 음성 인식이 한국어를 지원하지 않습니다.")
            }

            // 네트워크 등 — 몇 번은 다시 해 보고, 계속 실패하면 멈춘다
            else -> if (++failures >= 5) {
                stop(); onStopped("음성 인식이 계속 실패합니다 (오류 $error). 네트워크를 확인해 주세요.")
            } else restart(1000)
        }
    }

    override fun onPartialResults(partial: Bundle) { /* 중간 결과를 흐리게 보여 줘도 좋다 */ }
    override fun onReadyForSpeech(params: Bundle?) {}
    override fun onBeginningOfSpeech() {}
    override fun onEndOfSpeech() {}             // 여기서 재시작하지 않는다 — 결과가 오기 전이다
    override fun onRmsChanged(rmsdB: Float) {}
    override fun onBufferReceived(buffer: ByteArray?) {}
    override fun onEvent(eventType: Int, params: Bundle?) {}
}
```

## 빠뜨리기 쉬운 것들

| | |
|---|---|
| 매니페스트에 `<queries>` | Android 11+ 대상이면 없을 때 인식 서비스가 안 보인다 |
| 앱 폰에 **통화가 걸려 있지 않은가** | 걸려 있으면 무음만 들어온다. 오류도 안 난다 |
| 재시작은 `onResults` / `onError`에서 | `onEndOfSpeech`는 결과가 오기 **전**이라, 거기서 다시 시작하면 문장이 버려진다 |
| `stop()`에서 `listening = false`를 **먼저** | 안 그러면 `onError` → `restart()`로 되살아난다 |
| 재시작에 **지연을 둔다**(300ms) | 곧바로 부르면 `ERROR_RECOGNIZER_BUSY` |
| **영구 오류에서는 멈춘다** | 권한·언어 오류는 다시 해도 같다. 헛돌지 않게 |
| 인식 결과를 **이어 붙인다** | 덮어쓰면 마지막 문장만 남는다 |
| `onDestroy`에서 `stop()` | 안 하면 화면을 나가도 마이크가 살아 있다 |

## 텍스트를 이어 붙일 때

```kotlin
val merged = if (current.isBlank()) new else "$current $new"
```

문장 사이에 **공백 하나**를 넣는다. 붙여 쓰면 "인출해안전계좌로"처럼 되어
키워드가 안 걸린다.

## 권한

`RECORD_AUDIO`는 **쓰기 직전에** 요청한다. 거부당해도 앱을 막지 않는다 —
텍스트 직접 입력으로 계속 쓸 수 있게 한다.

## 기기에 따라 다른 것 (실제 기기에서 확인한다)

- **시작할 때마다 '띵' 소리**가 나는 기기가 있다. 계속 재시작하므로 몇 초마다
  울릴 수 있다. 거슬리면 받아쓰는 동안 알림음 볼륨을 잠시 낮춘다
- 기본 음성 인식은 보통 **네트워크를 쓴다.** 폰은 어차피 백엔드와 같은 무선망에
  있으니 시연에는 지장이 없다

## 한계를 인정한다

전시장은 시끄럽다. 받아쓰기가 "검찰청"을 "거찰청"으로 옮기면 키워드가 안 걸린다.
**그래서 텍스트를 손으로 고칠 수 있어야 한다는 것이 화면 요구사항이다.**
녹음 재생을 전시 기본 경로로 삼는 것도 같은 이유다 — 대본과 볼륨을 통제할 수 있다.
