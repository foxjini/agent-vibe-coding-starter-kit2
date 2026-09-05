/**
 * Web Audio API 기반 실시간 K-POP 노래방 반주(MR) 합성 엔진
 * 드럼(킥, 스네어, 하이햇), 베이스라인, 코드 신스 패드, 인트로 리프를 실시간 다채널 연주
 */

export interface SongChordsConfig {
  bpm: number;
  rootFrequencies: number[][]; // 4마디 코드 진행 (주파수 배열)
  bassNotes: number[]; // 베이스 근음 주파수
  style: "rock" | "dance" | "acoustic" | "ballad";
}

// 각 곡별 고유의 BPM 및 코드 진행 정의
export const SONG_MR_CONFIGS: Record<string, SongChordsConfig> = {
  고민중독: {
    bpm: 138,
    // E - B - C#m - A 펑크 록 진행
    rootFrequencies: [
      [329.63, 415.3, 493.88], // E4
      [246.94, 311.13, 369.99], // B3
      [277.18, 329.63, 415.3], // C#m
      [220.0, 277.18, 329.63], // A3
    ],
    bassNotes: [82.41, 61.74, 69.3, 55.0],
    style: "rock",
  },
  "한 페이지가 될 수 있게": {
    bpm: 136,
    // D - A - Bm - G 활기찬 밴드 록
    rootFrequencies: [
      [293.66, 369.99, 440.0], // D4
      [220.0, 277.18, 329.63], // A3
      [246.94, 293.66, 369.99], // Bm
      [196.0, 246.94, 293.66], // G3
    ],
    bassNotes: [73.42, 55.0, 61.74, 48.99],
    style: "rock",
  },
  "Hype Boy": {
    bpm: 100,
    // F - G - Em - Am 트렌디 R&B/댄스
    rootFrequencies: [
      [349.23, 440.0, 523.25], // F4
      [392.0, 493.88, 587.33], // G4
      [329.63, 392.0, 493.88], // Em4
      [440.0, 523.25, 659.25], // Am4
    ],
    bassNotes: [87.31, 98.0, 82.41, 110.0],
    style: "dance",
  },
  "I AM": {
    bpm: 128,
    // Gm - Eb - Bb - F 파워풀 댄스 팝
    rootFrequencies: [
      [392.0, 466.16, 587.33], // Gm
      [311.13, 392.0, 466.16], // Eb
      [233.08, 293.66, 349.23], // Bb
      [349.23, 440.0, 523.25], // F
    ],
    bassNotes: [98.0, 77.78, 58.27, 87.31],
    style: "dance",
  },
  신호등: {
    bpm: 95,
    // C - G - Am - F 따뜻한 어쿠스틱 스윙
    rootFrequencies: [
      [261.63, 329.63, 392.0], // C4
      [196.0, 246.94, 293.66], // G3
      [220.0, 261.63, 329.63], // Am3
      [174.61, 220.0, 261.63], // F3
    ],
    bassNotes: [65.41, 48.99, 55.0, 43.65],
    style: "acoustic",
  },
  "사건의 지평선": {
    bpm: 124,
    // C#m - A - E - B 드라마틱 발라드 록
    rootFrequencies: [
      [277.18, 329.63, 415.3], // C#m
      [220.0, 277.18, 329.63], // A
      [329.63, 415.3, 493.88], // E
      [246.94, 311.13, 369.99], // B
    ],
    bassNotes: [69.3, 55.0, 82.41, 61.74],
    style: "ballad",
  },
  Supernova: {
    bpm: 130,
    // Dm - Bb - Gm - A 강렬한 일렉트로닉 댄스
    rootFrequencies: [
      [293.66, 349.23, 440.0], // Dm
      [233.08, 293.66, 349.23], // Bb
      [196.0, 233.08, 293.66], // Gm
      [220.0, 277.18, 329.63], // A
    ],
    bassNotes: [73.42, 58.27, 48.99, 55.0],
    style: "dance",
  },
  "다시 만나": {
    bpm: 118,
    // C - G - Am - F 감동적인 졸업/퇴실 팝
    rootFrequencies: [
      [261.63, 329.63, 392.0], // C
      [196.0, 246.94, 293.66], // G
      [220.0, 261.63, 329.63], // Am
      [174.61, 220.0, 261.63], // F
    ],
    bassNotes: [65.41, 48.99, 55.0, 43.65],
    style: "ballad",
  },
};

export class KaraokeAccompanimentEngine {
  private ctx: AudioContext | null = null;
  private masterGain: GainNode | null = null;
  private isRunning = false;
  private currentStep = 0;
  private timerId: NodeJS.Timeout | null = null;
  private volume = 0.65;

  init() {
    if (typeof window === "undefined") return;
    if (!this.ctx) {
      const AudioCtxClass =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      this.ctx = new AudioCtxClass();
      this.masterGain = this.ctx.createGain();
      this.masterGain.gain.setValueAtTime(this.volume, this.ctx.currentTime);
      this.masterGain.connect(this.ctx.destination);
    }
  }

  setVolume(vol: number) {
    this.volume = Math.max(0, Math.min(1, vol));
    if (this.masterGain && this.ctx) {
      this.masterGain.gain.setValueAtTime(this.volume, this.ctx.currentTime);
    }
  }

  start(songTitle: string) {
    this.init();
    if (!this.ctx || !this.masterGain) return;
    if (this.ctx.state === "suspended") {
      this.ctx.resume();
    }

    this.stop();
    this.isRunning = true;
    this.currentStep = 0;

    const config = SONG_MR_CONFIGS[songTitle] || SONG_MR_CONFIGS["고민중독"];
    const stepIntervalMs = (60 / config.bpm / 4) * 1000; // 16분음표 단위 틱

    this.timerId = setInterval(() => {
      if (!this.isRunning || !this.ctx || !this.masterGain) return;
      this.tick(config);
      this.currentStep = (this.currentStep + 1) % 64; // 4마디 (16박자 * 4 = 64틱)
    }, stepIntervalMs);
  }

  stop() {
    this.isRunning = false;
    if (this.timerId) {
      clearInterval(this.timerId);
      this.timerId = null;
    }
  }

  private tick(config: SongChordsConfig) {
    if (!this.ctx || !this.masterGain) return;

    const barIndex = Math.floor(this.currentStep / 16) % 4; // 현재 몇 번째 마디인가 (0, 1, 2, 3)
    const beatIndex = Math.floor((this.currentStep % 16) / 4); // 4분음표 비트 (0, 1, 2, 3)
    const subStep = this.currentStep % 4; // 16분음표 쪼갬 (0, 1, 2, 3)

    const now = this.ctx.currentTime;

    // 1. 드럼 파트 (16비트 K-POP 그루브)
    // 킥: 1박(0), 3박(2), 혹은 록 스타일 싱코페이션
    if ((beatIndex === 0 || beatIndex === 2) && subStep === 0) {
      this.playKick(now);
    }
    // 스네어: 2박(1), 4박(3)
    if ((beatIndex === 1 || beatIndex === 3) && subStep === 0) {
      this.playSnare(now);
    }
    // 하이햇: 매 8분음표(subStep 0, 2)마다 찰랑거림
    if (subStep === 0 || subStep === 2) {
      this.playHiHat(now, subStep === 0 ? 0.08 : 0.04);
    }

    // 2. 베이스 파트 (각 마디의 코드 근음 연주)
    if (subStep === 0 || (subStep === 2 && config.style === "rock")) {
      const bassFreq = config.bassNotes[barIndex] || 65.41;
      this.playBass(bassFreq, now, config.style);
    }

    // 3. 화음 코드 신스 패드 (마디 시작 또는 반주 스트로크)
    if (subStep === 0) {
      const chord = config.rootFrequencies[barIndex] || [261.63, 329.63, 392.0];
      this.playChord(chord, now, config.style);
    }
  }

  // 킥 드럼 합성
  private playKick(time: number) {
    if (!this.ctx || !this.masterGain) return;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();

    osc.frequency.setValueAtTime(140, time);
    osc.frequency.exponentialRampToValueAtTime(38, time + 0.12);

    gain.gain.setValueAtTime(0.35, time);
    gain.gain.exponentialRampToValueAtTime(0.001, time + 0.13);

    osc.connect(gain);
    gain.connect(this.masterGain);
    osc.start(time);
    osc.stop(time + 0.14);
  }

  // 스네어 드럼 합성
  private playSnare(time: number) {
    if (!this.ctx || !this.masterGain) return;
    // 노이즈 버퍼로 바스락거리는 스네어 잔향 생성
    const bufferSize = Math.floor(this.ctx.sampleRate * 0.15);
    const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < bufferSize; i++) {
      data[i] = Math.random() * 2 - 1;
    }

    const noise = this.ctx.createBufferSource();
    noise.buffer = buffer;

    const filter = this.ctx.createBiquadFilter();
    filter.type = "highpass";
    filter.frequency.setValueAtTime(900, time);

    const gain = this.ctx.createGain();
    gain.gain.setValueAtTime(0.25, time);
    gain.gain.exponentialRampToValueAtTime(0.001, time + 0.15);

    noise.connect(filter);
    filter.connect(gain);
    gain.connect(this.masterGain);
    noise.start(time);
    noise.stop(time + 0.16);

    // 스네어 몸체 톤
    const osc = this.ctx.createOscillator();
    const oscGain = this.ctx.createGain();
    osc.type = "triangle";
    osc.frequency.setValueAtTime(190, time);
    osc.frequency.exponentialRampToValueAtTime(80, time + 0.08);

    oscGain.gain.setValueAtTime(0.2, time);
    oscGain.gain.exponentialRampToValueAtTime(0.001, time + 0.08);

    osc.connect(oscGain);
    oscGain.connect(this.masterGain);
    osc.start(time);
    osc.stop(time + 0.09);
  }

  // 하이햇 합성
  private playHiHat(time: number, vol = 0.06) {
    if (!this.ctx || !this.masterGain) return;
    const bufferSize = Math.floor(this.ctx.sampleRate * 0.04);
    const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < bufferSize; i++) {
      data[i] = Math.random() * 2 - 1;
    }

    const noise = this.ctx.createBufferSource();
    noise.buffer = buffer;

    const filter = this.ctx.createBiquadFilter();
    filter.type = "highpass";
    filter.frequency.setValueAtTime(7000, time);

    const gain = this.ctx.createGain();
    gain.gain.setValueAtTime(vol, time);
    gain.gain.exponentialRampToValueAtTime(0.001, time + 0.04);

    noise.connect(filter);
    filter.connect(gain);
    gain.connect(this.masterGain);
    noise.start(time);
    noise.stop(time + 0.05);
  }

  // 베이스라인 합성
  private playBass(freq: number, time: number, style: string) {
    if (!this.ctx || !this.masterGain) return;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();

    osc.type = style === "dance" ? "sawtooth" : "triangle";
    osc.frequency.setValueAtTime(freq, time);

    gain.gain.setValueAtTime(0.22, time);
    gain.gain.exponentialRampToValueAtTime(0.001, time + (style === "rock" ? 0.22 : 0.35));

    osc.connect(gain);
    gain.connect(this.masterGain);
    osc.start(time);
    osc.stop(time + 0.36);
  }

  // 화음 코드 패드 합성
  private playChord(notes: number[], time: number, style: string) {
    if (!this.ctx || !this.masterGain) return;
    notes.forEach((freq) => {
      const osc = this.ctx!.createOscillator();
      const gain = this.ctx!.createGain();

      osc.type = style === "acoustic" ? "sine" : "triangle";
      osc.frequency.setValueAtTime(freq, time);

      const dur = style === "rock" ? 0.28 : 0.45;
      gain.gain.setValueAtTime(0.09, time);
      gain.gain.exponentialRampToValueAtTime(0.001, time + dur);

      osc.connect(gain);
      gain.connect(this.masterGain!);
      osc.start(time);
      osc.stop(time + dur + 0.02);
    });
  }
}
