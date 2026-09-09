/**
 * 마이크 실시간 음정/음량 분석 + 노래방 채점 모듈 (Web Audio API)
 *
 * ── 이전 버전의 문제와 수정 ────────────────────────────────────────
 *  · 점수가 성량과 난수로만 정해져서 노래를 부르지 않아도 83~99점이 나왔다.
 *    ✅ 음정 정확도(반음 기준 편차)·지속성·성량·표현력 4개 항목으로 나눠 계산하고,
 *       실제로 소리를 내지 않았으면 낮은 점수와 안내가 나가도록 바꿨다.
 *  · 곡을 연달아 부르면 앞 곡의 통계가 남아 있었다. ✅ resetScore()를 공개.
 *  · 자기상관 피치 검출이 정수 지연만 봐서 고음에서 오차가 컸다.
 *    ✅ 포물선 보간(parabolic interpolation)으로 소수점 지연까지 추정.
 */

export interface AudioAnalysisResult {
  volume: number; // 0 ~ 100 RMS 볼륨 레벨
  pitch: number; // Hz 주파수 (0이면 비음성 구간)
  note: string; // 계이름 (C, C#, D ...)
  /** 가장 가까운 반음에서 얼마나 벗어났는지 (-50 ~ +50 cents) — 음정 게이지용 */
  cents: number;
}

/** 항목별 점수 (합계가 최종 점수) */
export interface ScoreBreakdown {
  /** 음정 정확도 (0~35) */
  pitch: number;
  /** 박자·지속성 (0~30) */
  timing: number;
  /** 성량 (0~20) */
  volume: number;
  /** 표현력 — 음역 활용과 비브라토 (0~15) */
  expression: number;
}

export interface FinalScore {
  score: number;
  comment: string;
  rank: string;
  breakdown: ScoreBreakdown;
  /** 마이크로 실제 노래가 감지됐는지 — false면 안내 문구를 다르게 띄운다 */
  sangSomething: boolean;
}

const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

/** 주변 소음을 재기 전에 쓰는 기본 임계값 */
const DEFAULT_VOICE_THRESHOLD = 12;

/**
 * 측정한 배경 소음 위에 얹는 여유값.
 * 이 값이 너무 작으면 소음을 노래로 세고, 너무 크면 작게 부른 소리를 놓친다.
 * 교실·전시장에서 직접 불러 보며 조정할 것 (부록G의 리허설 항목).
 */
const NOISE_MARGIN = 8;

/** 소음 측정 기본 시간 (ms) */
const BASELINE_DURATION_MS = 1500;

export class KaraokeAudioScorer {
  private audioCtx: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private micStream: MediaStream | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private animFrameId: number | null = null;
  private onDataCallback: ((data: AudioAnalysisResult) => void) | null = null;

  // ── 채점 누적 통계 ──
  private sampleCount = 0;
  private voicedFrames = 0;
  private volumeSum = 0;
  private voicedVolumeSum = 0;
  private centsAbsSum = 0; // 반음 이탈량 합 (음정 정확도)
  private semitoneMin = Infinity; // 사용한 최저음 (MIDI 번호)
  private semitoneMax = -Infinity; // 사용한 최고음
  private directionChanges = 0; // 피치가 오르내린 횟수 (비브라토·표현력)
  private lastPitch = 0;
  private lastDirection = 0;
  // 채점 판정은 "몇 프레임"이 아니라 "몇 초 불렀는가"로 한다.
  // 실제 마이크(약 60fps)와 가상보컬(약 6.7fps)의 프레임 레이트가 달라
  // 프레임 수로 재면 같은 시간을 불러도 결과가 달라지기 때문이다.
  private startedAt = 0;
  private lastSampleAt = 0;

  // 발성으로 인정할 최소 음량. 교실·전시장은 조용한 방보다 배경 소음이 커서
  // 고정값을 쓰면 소음을 노래로 잘못 세거나(오탐) 작게 부른 소리를 놓친다(미탐).
  // 노래 시작 전 주변 소음을 재서 이 값을 환경에 맞게 올린다.
  private voiceThreshold = DEFAULT_VOICE_THRESHOLD;
  private baselineNoise = 0;
  private isMeasuringBaseline = false;
  private baselineSamples: number[] = [];

  // 일시정지 동안은 통계를 쌓지 않는다 (안 부른 시간으로 집계되면 박자 점수가 깎인다)
  private paused = false;

  /* ── 마이크 ─────────────────────────────────────────────── */

  async startMicrophone(onData: (data: AudioAnalysisResult) => void): Promise<boolean> {
    this.resetScore();
    this.onDataCallback = onData;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          // 노래 목소리를 깎지 않도록 잡음 제거·자동 게인은 끈다
          noiseSuppression: false,
          autoGainControl: false,
        },
      });

      this.micStream = stream;
      const Ctor =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      this.audioCtx = new Ctor();
      this.analyser = this.audioCtx.createAnalyser();
      this.analyser.fftSize = 2048;
      this.analyser.smoothingTimeConstant = 0.6;

      this.source = this.audioCtx.createMediaStreamSource(stream);
      this.source.connect(this.analyser);

      this.analyzeLoop();
      return true;
    } catch (err) {
      console.warn("마이크를 사용할 수 없습니다:", err);
      return false;
    }
  }

  stopMicrophone() {
    if (this.animFrameId) {
      cancelAnimationFrame(this.animFrameId);
      this.animFrameId = null;
    }
    if (this.micStream) {
      this.micStream.getTracks().forEach((t) => t.stop());
      this.micStream = null;
    }
    if (this.audioCtx) {
      void this.audioCtx.close();
      this.audioCtx = null;
    }
    this.source = null;
    this.analyser = null;
  }

  get isRunning() {
    return this.animFrameId !== null;
  }

  /** 현재 적용 중인 발성 인식 임계값 (화면 표시용) */
  get threshold() {
    return { voice: this.voiceThreshold, baseline: this.baselineNoise };
  }

  /* ── 일시정지 / 재개 ────────────────────────────────────────
   * 영상이 멈춘 동안 분석을 세면 그 시간이 "안 부른 시간"이 되어
   * 박자 점수가 부당하게 깎인다. 마이크 스트림은 그대로 두고
   * 통계 집계만 멈춘다 (다시 권한을 묻지 않기 위해).
   * ──────────────────────────────────────────────────────── */

  pauseAnalysis() {
    this.paused = true;
    // AudioContext까지 재우면 CPU도 아낄 수 있다
    if (this.audioCtx?.state === "running") void this.audioCtx.suspend();
  }

  resumeAnalysis() {
    this.paused = false;
    if (this.audioCtx?.state === "suspended") void this.audioCtx.resume();
  }

  /**
   * 노래 시작 전 주변 소음을 재서 발성 인식 임계값을 환경에 맞게 정한다.
   *
   * 교실이나 전시장은 조용한 방보다 배경 소음이 커서, 고정 임계값을 쓰면
   * 에어컨 소리를 노래로 세거나(오탐) 작게 부른 소리를 놓친다(미탐).
   *
   * @returns 측정한 배경 소음과 결정된 임계값
   */
  async measureBaseline(durationMs = BASELINE_DURATION_MS): Promise<{ baseline: number; threshold: number }> {
    if (!this.isRunning) {
      // 마이크가 없으면 기본값을 그대로 쓴다
      return { baseline: 0, threshold: this.voiceThreshold };
    }

    this.baselineSamples = [];
    this.isMeasuringBaseline = true;

    await new Promise((resolve) => setTimeout(resolve, durationMs));

    this.isMeasuringBaseline = false;

    const samples = this.baselineSamples;
    this.baselineSamples = [];

    if (samples.length === 0) {
      return { baseline: 0, threshold: this.voiceThreshold };
    }

    // 평균보다 상위값을 봐야 간헐적인 소음(문 여닫는 소리)에 덜 휘둘린다
    const sorted = [...samples].sort((a, b) => a - b);
    const p80 = sorted[Math.floor(sorted.length * 0.8)] ?? sorted[sorted.length - 1];

    this.baselineNoise = Math.round(p80);
    this.voiceThreshold = Math.max(DEFAULT_VOICE_THRESHOLD, this.baselineNoise + NOISE_MARGIN);

    return { baseline: this.baselineNoise, threshold: this.voiceThreshold };
  }

  /* ── 분석 루프 ──────────────────────────────────────────── */

  private analyzeLoop = () => {
    if (!this.analyser) return;

    const size = this.analyser.fftSize;
    const timeData = new Float32Array(size);
    this.analyser.getFloatTimeDomainData(timeData);

    // RMS 볼륨
    let sum = 0;
    for (let i = 0; i < size; i++) sum += timeData[i] * timeData[i];
    const rms = Math.sqrt(sum / size);
    const volume = Math.min(100, Math.round(rms * 400));

    // 주변 소음 측정 구간 — 통계를 쌓지 않고 소음 크기만 모은다
    if (this.isMeasuringBaseline) {
      this.baselineSamples.push(volume);
      this.onDataCallback?.({ volume, pitch: 0, note: "-", cents: 0 });
      this.animFrameId = requestAnimationFrame(this.analyzeLoop);
      return;
    }

    // 일시정지 중에는 화면 미터만 갱신하고 채점 통계는 건드리지 않는다
    if (this.paused) {
      this.onDataCallback?.({ volume, pitch: 0, note: "-", cents: 0 });
      this.animFrameId = requestAnimationFrame(this.analyzeLoop);
      return;
    }

    const pitch = this.detectPitch(timeData, this.audioCtx?.sampleRate ?? 44100);

    // 반음 기준 편차(cents) 계산
    let cents = 0;
    let note = "-";
    if (pitch > 0) {
      const midi = 69 + 12 * Math.log2(pitch / 440);
      const nearest = Math.round(midi);
      cents = Math.round((midi - nearest) * 100);
      note = NOTE_NAMES[((nearest % 12) + 12) % 12];
    }

    // 통계 누적
    this.markSample();
    this.volumeSum += volume;

    const voiced = volume > this.voiceThreshold && pitch > 70 && pitch < 1400;
    if (voiced) {
      this.voicedFrames++;
      this.voicedVolumeSum += volume;
      this.centsAbsSum += Math.abs(cents);

      const midi = 69 + 12 * Math.log2(pitch / 440);
      this.semitoneMin = Math.min(this.semitoneMin, midi);
      this.semitoneMax = Math.max(this.semitoneMax, midi);

      if (this.lastPitch > 0) {
        const diff = pitch - this.lastPitch;
        const dir = Math.abs(diff) < 1.5 ? 0 : diff > 0 ? 1 : -1;
        if (dir !== 0 && this.lastDirection !== 0 && dir !== this.lastDirection) {
          this.directionChanges++;
        }
        if (dir !== 0) this.lastDirection = dir;
      }
      this.lastPitch = pitch;
    }

    this.onDataCallback?.({ volume, pitch, note, cents });
    this.animFrameId = requestAnimationFrame(this.analyzeLoop);
  };

  /**
   * 자기상관법(autocorrelation) 피치 검출 + 포물선 보간
   */
  private detectPitch(buffer: Float32Array, sampleRate: number): number {
    const SIZE = buffer.length;

    let rms = 0;
    for (let i = 0; i < SIZE; i++) rms += buffer[i] * buffer[i];
    rms = Math.sqrt(rms / SIZE);
    if (rms < 0.015) return 0; // 침묵

    // 사람 목소리 범위(70~1400Hz)에 해당하는 지연 구간만 탐색
    const minLag = Math.floor(sampleRate / 1400);
    const maxLag = Math.min(Math.floor(sampleRate / 70), Math.floor(SIZE / 2));

    let bestLag = -1;
    let bestCorr = 0;
    let prevCorr = 0;
    const corr = new Float32Array(maxLag + 2);

    for (let lag = minLag; lag <= maxLag; lag++) {
      let c = 0;
      let normA = 0;
      let normB = 0;
      for (let i = 0; i < SIZE - lag; i++) {
        c += buffer[i] * buffer[i + lag];
        normA += buffer[i] * buffer[i];
        normB += buffer[i + lag] * buffer[i + lag];
      }
      // 정규화 — 신호 세기와 무관하게 0~1로 비교할 수 있다
      const norm = Math.sqrt(normA * normB);
      const value = norm > 0 ? c / norm : 0;
      corr[lag] = value;

      // 첫 번째 뚜렷한 봉우리를 찾으면 그것이 기본 주파수 (배음 오검출 방지)
      if (value > 0.9 && value < prevCorr && bestLag === -1) {
        bestLag = lag - 1;
        bestCorr = prevCorr;
        break;
      }
      if (value > bestCorr) {
        bestCorr = value;
        bestLag = lag;
      }
      prevCorr = value;
    }

    if (bestLag <= minLag || bestCorr < 0.55) return 0;

    // 포물선 보간으로 소수점 지연까지 추정 → 고음 정확도 개선
    const y0 = corr[bestLag - 1] ?? bestCorr;
    const y1 = corr[bestLag];
    const y2 = corr[bestLag + 1] ?? bestCorr;
    const denom = 2 * (2 * y1 - y0 - y2);
    const shift = denom !== 0 ? (y2 - y0) / denom : 0;
    const refined = bestLag + Math.max(-1, Math.min(1, shift));

    const freq = sampleRate / refined;
    return freq > 70 && freq < 1400 ? Math.round(freq) : 0;
  }

  /* ── 채점 ───────────────────────────────────────────────── */

  /** 프레임 1개를 기록하고 경과 시간을 갱신한다 */
  private markSample() {
    const now = Date.now();
    if (this.startedAt === 0) this.startedAt = now;
    this.lastSampleAt = now;
    this.sampleCount++;
  }

  /** 분석이 진행된 총 시간(초) */
  private get elapsedSec(): number {
    if (this.startedAt === 0) return 0;
    return Math.max(0, (this.lastSampleAt - this.startedAt) / 1000);
  }

  resetScore() {
    // voiceThreshold는 일부러 초기화하지 않는다.
    // 곡이 바뀌어도 주변 환경은 그대로이므로 측정값을 재사용한다.
    this.paused = false;
    this.startedAt = 0;
    this.lastSampleAt = 0;
    this.sampleCount = 0;
    this.voicedFrames = 0;
    this.volumeSum = 0;
    this.voicedVolumeSum = 0;
    this.centsAbsSum = 0;
    this.semitoneMin = Infinity;
    this.semitoneMax = -Infinity;
    this.directionChanges = 0;
    this.lastPitch = 0;
    this.lastDirection = 0;
  }

  /** 가상보컬 모드에서 시뮬레이션 프레임을 통계에 넣을 때 사용 */
  feedSimulatedFrame(volume: number, pitch: number) {
    this.markSample();
    this.volumeSum += volume;
    if (volume > this.voiceThreshold && pitch > 70) {
      this.voicedFrames++;
      this.voicedVolumeSum += volume;
      this.centsAbsSum += 8 + Math.random() * 14; // 사람이 부른 정도의 편차
      const midi = 69 + 12 * Math.log2(pitch / 440);
      this.semitoneMin = Math.min(this.semitoneMin, midi);
      this.semitoneMax = Math.max(this.semitoneMax, midi);
      if (Math.random() < 0.35) this.directionChanges++;
    }
  }

  calculateFinalScore(): FinalScore {
    const frames = this.sampleCount;
    const voicedRatio = frames > 0 ? this.voicedFrames / frames : 0;
    // 실제로 소리를 낸 시간(초) — 2초 이상이면 "불렀다"고 본다
    const voicedSec = voicedRatio * this.elapsedSec;
    const sangSomething = voicedSec >= 2 && voicedRatio > 0.05;

    // 아예 부르지 않은 경우 — 점수를 만들어내지 않고 사실대로 알린다
    if (!sangSomething) {
      return {
        score: 0,
        comment: "마이크로 들어온 노랫소리가 없었습니다. 마이크 연결을 확인해 주세요!",
        rank: "-",
        breakdown: { pitch: 0, timing: 0, volume: 0, expression: 0 },
        sangSomething: false,
      };
    }

    // ① 음정 정확도 (35점) — 반음에서 평균 몇 cents 벗어났는가
    const avgCents = this.centsAbsSum / this.voicedFrames; // 0(완벽) ~ 50(최악)
    const pitchScore = Math.round(35 * Math.max(0, 1 - avgCents / 42));

    // ② 박자·지속성 (30점) — 반주가 흐르는 동안 얼마나 꾸준히 불렀는가
    //    노래에는 간주·쉼표가 있으므로 55% 이상 부르면 만점으로 본다
    const timingScore = Math.round(30 * Math.min(1, voicedRatio / 0.55));

    // ③ 성량 (20점) — 목소리를 낼 때의 평균 크기
    const avgVoicedVol = this.voicedVolumeSum / this.voicedFrames;
    const volumeScore = Math.round(20 * Math.min(1, avgVoicedVol / 55));

    // ④ 표현력 (15점) — 음역을 얼마나 쓰고 비브라토가 있는가
    const range = this.semitoneMax - this.semitoneMin; // 반음 단위
    const rangeScore = Math.min(1, range / 14) * 9;
    const vibratoRate = this.directionChanges / Math.max(1, voicedSec); // 초당 방향 전환
    const vibratoScore = Math.min(1, vibratoRate / 5) * 6;
    const expressionScore = Math.round(rangeScore + vibratoScore);

    const raw = pitchScore + timingScore + volumeScore + expressionScore;
    // 노래방 기기 특유의 격려 보정 — 실제로 불렀다면 최소 60점은 준다
    const score = Math.max(60, Math.min(100, raw));

    let comment = "끝까지 완창했어요! 다음엔 더 잘할 수 있습니다 💪";
    let rank = "B";
    if (score >= 97) {
      comment = "🏆 전교 1등 가수! 음정·박자 모두 완벽했습니다!";
      rank = "SSS";
    } else if (score >= 93) {
      comment = "🎤 음정이 아주 정확했어요! 무대 체질입니다!";
      rank = "SS";
    } else if (score >= 88) {
      comment = "👏 폭발적인 가창력! 관객을 사로잡았습니다!";
      rank = "S";
    } else if (score >= 82) {
      comment = "✨ 안정적인 음정과 성량! 훌륭한 무대였어요!";
      rank = "A+";
    } else if (score >= 74) {
      comment = "🎵 즐겁게 잘 불렀어요! 후렴을 조금 더 크게 불러 보세요!";
      rank = "A";
    }

    return {
      score,
      comment,
      rank,
      breakdown: {
        pitch: pitchScore,
        timing: timingScore,
        volume: volumeScore,
        expression: expressionScore,
      },
      sangSomething: true,
    };
  }

  /* ── 효과음 ─────────────────────────────────────────────── */

  /** 효과음은 짧게 쓰고 바로 닫는다 (AudioContext 개수 제한 회피) */
  private static withCtx(run: (ctx: AudioContext) => number) {
    try {
      const Ctor =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new Ctor();
      const lifetimeMs = run(ctx);
      setTimeout(() => void ctx.close(), lifetimeMs);
    } catch {
      /* 오디오를 못 쓰는 환경에서는 조용히 건너뛴다 */
    }
  }

  static playFanfareSound() {
    KaraokeAudioScorer.withCtx((ctx) => {
      const notes = [
        { freq: 523.25, time: 0.0, dur: 0.15 },
        { freq: 659.25, time: 0.15, dur: 0.15 },
        { freq: 783.99, time: 0.3, dur: 0.15 },
        { freq: 1046.5, time: 0.45, dur: 0.35 },
        { freq: 783.99, time: 0.8, dur: 0.15 },
        { freq: 1046.5, time: 0.95, dur: 0.7 },
      ];
      notes.forEach(({ freq, time, dur }) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "triangle";
        osc.frequency.setValueAtTime(freq, ctx.currentTime + time);
        gain.gain.setValueAtTime(0.0001, ctx.currentTime + time);
        gain.gain.exponentialRampToValueAtTime(0.2, ctx.currentTime + time + 0.01);
        gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + time + dur);
        osc.connect(gain).connect(ctx.destination);
        osc.start(ctx.currentTime + time);
        osc.stop(ctx.currentTime + time + dur);
      });
      return 2200;
    });
  }

  static playDrumrollSound() {
    KaraokeAudioScorer.withCtx((ctx) => {
      for (let i = 0; i < 20; i++) {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "sine";
        const t = ctx.currentTime + i * 0.055;
        osc.frequency.setValueAtTime(130 + Math.random() * 50, t);
        gain.gain.setValueAtTime(0.13, t);
        gain.gain.exponentialRampToValueAtTime(0.001, t + 0.05);
        osc.connect(gain).connect(ctx.destination);
        osc.start(t);
        osc.stop(t + 0.05);
      }
      return 1600;
    });
  }
}
