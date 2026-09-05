/**
 * Web Audio API 기반 마이크 실시간 음정/음량 분석기 및 노래방 점수 채점 모듈
 */

export interface AudioAnalysisResult {
  volume: number; // 0 ~ 100 RMS 볼륨 레벨
  pitch: number; // Hz 주파수 (0이면 비음성 구간)
  note: string; // 계이름 (C, D, E, F, G, A, B)
}

export class KaraokeAudioScorer {
  private audioCtx: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private micStream: MediaStream | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private animFrameId: number | null = null;

  // 채점 누적 데이터
  private sampleCount = 0;
  private activeVocalSamples = 0;
  private volumeSum = 0;
  private pitchVariations = 0;
  private lastPitch = 0;

  // 콜백
  private onDataCallback: ((data: AudioAnalysisResult) => void) | null = null;

  /**
   * 실제 마이크 스트림 시작
   */
  async startMicrophone(onData: (data: AudioAnalysisResult) => void): Promise<boolean> {
    this.resetScoreData();
    this.onDataCallback = onData;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: false,
          autoGainControl: true,
        },
      });

      this.micStream = stream;
      const AudioCtxClass =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      this.audioCtx = new AudioCtxClass();
      this.analyser = this.audioCtx.createAnalyser();
      this.analyser.fftSize = 2048;
      this.analyser.smoothingTimeConstant = 0.8;

      this.source = this.audioCtx.createMediaStreamSource(stream);
      this.source.connect(this.analyser);

      this.analyzeLoop();
      return true;
    } catch (err) {
      console.warn("Microphone access denied or unavailable:", err);
      return false;
    }
  }

  /**
   * 분석 루프
   */
  private analyzeLoop = () => {
    if (!this.analyser) return;

    const bufferLength = this.analyser.fftSize;
    const timeData = new Float32Array(bufferLength);
    this.analyser.getFloatTimeDomainData(timeData);

    // 1. RMS 볼륨 계산
    let sum = 0;
    for (let i = 0; i < bufferLength; i++) {
      sum += timeData[i] * timeData[i];
    }
    const rms = Math.sqrt(sum / bufferLength);
    // 데시벨 정규화 (0 ~ 100)
    const volume = Math.min(100, Math.round(rms * 400));

    // 2. 피치(음높이 주파수) 검출 - Autocorrelation (자기상관법)
    const pitch = this.detectPitch(timeData, this.audioCtx?.sampleRate || 44100);
    const note = this.frequencyToNote(pitch);

    // 3. 점수 통계 누적
    this.sampleCount++;
    this.volumeSum += volume;
    if (volume > 15 && pitch > 70 && pitch < 1200) {
      this.activeVocalSamples++;
      if (this.lastPitch > 0 && Math.abs(pitch - this.lastPitch) > 5) {
        this.pitchVariations++;
      }
      this.lastPitch = pitch;
    }

    if (this.onDataCallback) {
      this.onDataCallback({ volume, pitch, note });
    }

    this.animFrameId = requestAnimationFrame(this.analyzeLoop);
  };

  /**
   * 자기상관법(Autocorrelation)으로 음높이 주파수 검출
   */
  private detectPitch(buffer: Float32Array, sampleRate: number): number {
    const SIZE = buffer.length;
    let rms = 0;
    for (let i = 0; i < SIZE; i++) {
      rms += buffer[i] * buffer[i];
    }
    rms = Math.sqrt(rms / SIZE);
    if (rms < 0.02) return 0; // 너무 작으면 침묵으로 간주

    // Truncate buffer for positive correlation
    let r1 = 0;
    let r2 = SIZE - 1;
    const thres = 0.2;
    for (let i = 0; i < SIZE / 2; i++) {
      if (Math.abs(buffer[i]) < thres) {
        r1 = i;
        break;
      }
    }
    for (let i = 1; i < SIZE / 2; i++) {
      if (Math.abs(buffer[SIZE - i]) < thres) {
        r2 = SIZE - i;
        break;
      }
    }

    const buf = buffer.slice(r1, r2);
    const c = new Float32Array(buf.length);
    for (let i = 0; i < buf.length; i++) {
      for (let j = 0; j < buf.length - i; j++) {
        c[i] = c[i] + buf[j] * buf[j + i];
      }
    }

    let d = 0;
    while (c[d] > c[d + 1]) d++;
    let maxval = -1;
    let maxpos = -1;
    for (let i = d; i < buf.length; i++) {
      if (c[i] > maxval) {
        maxval = c[i];
        maxpos = i;
      }
    }
    const T0 = maxpos;
    if (T0 === 0) return 0;

    return Math.round(sampleRate / T0);
  }

  /**
   * 주파수를 계이름으로 변환
   */
  private frequencyToNote(freq: number): string {
    if (freq <= 0) return "-";
    const noteNames = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
    const semitone = 69 + 12 * Math.log2(freq / 440);
    const noteIdx = Math.round(semitone) % 12;
    return noteNames[noteIdx >= 0 ? noteIdx : noteIdx + 12];
  }

  /**
   * 마이크 중지
   */
  stopMicrophone() {
    if (this.animFrameId) {
      cancelAnimationFrame(this.animFrameId);
      this.animFrameId = null;
    }
    if (this.micStream) {
      this.micStream.getTracks().forEach((track) => track.stop());
      this.micStream = null;
    }
    if (this.audioCtx) {
      this.audioCtx.close();
      this.audioCtx = null;
    }
    this.source = null;
    this.analyser = null;
  }

  /**
   * 최종 노래방 점수 산출 (82 ~ 99점 범위)
   */
  calculateFinalScore(): { score: number; comment: string; rank: string } {
    const activityRatio = this.sampleCount > 0 ? this.activeVocalSamples / this.sampleCount : 0.4;
    const avgVol = this.sampleCount > 0 ? this.volumeSum / this.sampleCount : 30;

    // 점수 기본 베이스 82점 (노래방 특유의 격려 점수)
    let score = 82;

    // 성량 기여도 (최대 +9점)
    score += Math.min(9, Math.round((avgVol / 50) * 9));

    // 노래 지속 활성도 (최대 +8점)
    score += Math.min(8, Math.round(activityRatio * 16));

    // 흥/바이브레이션 가산점 (2~3점)
    score += Math.floor(Math.random() * 3);

    // 범위 제한 (83 ~ 99점)
    score = Math.max(83, Math.min(99, score));

    let comment = "열정적인 열창이었습니다!";
    let rank = "A";

    if (score >= 97) {
      comment = "🏆 전교 1등 가수급 보컬! 감동의 무대였습니다!";
      rank = "SSS";
    } else if (score >= 94) {
      comment = "🎤 완벽한 음정과 리듬감! 환상적인 무대 매너!";
      rank = "SS";
    } else if (score >= 90) {
      comment = "👏 폭풍 가창력! 관객을 사로잡는 열창이었습니다!";
      rank = "S";
    } else if (score >= 85) {
      comment = "✨ 훌륭한 음색과 무대 매너! 다음 곡도 기대돼요!";
      rank = "A+";
    }

    return { score, comment, rank };
  }

  private resetScoreData() {
    this.sampleCount = 0;
    this.activeVocalSamples = 0;
    this.volumeSum = 0;
    this.pitchVariations = 0;
    this.lastPitch = 0;
  }

  /**
   * 축하 팡파레 효과음 재생 (Web Audio API)
   */
  static playFanfareSound() {
    try {
      const AudioCtxClass =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new AudioCtxClass();

      // 경쾌한 아르페지오 팡파레 (도-미-솔-도-솔-도)
      const notes = [
        { freq: 523.25, time: 0.0, dur: 0.15 }, // C5
        { freq: 659.25, time: 0.15, dur: 0.15 }, // E5
        { freq: 783.99, time: 0.3, dur: 0.15 }, // G5
        { freq: 1046.5, time: 0.45, dur: 0.35 }, // C6
        { freq: 783.99, time: 0.8, dur: 0.15 }, // G5
        { freq: 1046.5, time: 0.95, dur: 0.6 }, // C6 (길게)
      ];

      notes.forEach(({ freq, time, dur }) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "triangle";
        osc.frequency.setValueAtTime(freq, ctx.currentTime + time);

        gain.gain.setValueAtTime(0.18, ctx.currentTime + time);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + time + dur);

        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(ctx.currentTime + time);
        osc.stop(ctx.currentTime + time + dur);
      });
    } catch {
      // ignore
    }
  }

  /**
   * 점수 발표 전 두구두구 드럼롤 사운드
   */
  static playDrumrollSound() {
    try {
      const AudioCtxClass =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new AudioCtxClass();

      for (let i = 0; i < 16; i++) {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "sine";
        const t = ctx.currentTime + i * 0.06;
        osc.frequency.setValueAtTime(140 + Math.random() * 40, t);
        gain.gain.setValueAtTime(0.12, t);
        gain.gain.exponentialRampToValueAtTime(0.001, t + 0.05);

        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(t);
        osc.stop(t + 0.05);
      }
    } catch {
      // ignore
    }
  }
}
