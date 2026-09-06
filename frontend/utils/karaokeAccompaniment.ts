/**
 * 내장 자동 반주(MR) 합성 엔진 — Web Audio API
 *
 * ⚠️ 이 엔진은 "원곡 반주"가 아니다.
 *    로컬 파일도 없고 유튜브도 연결되지 않을 때만 쓰는 **최후의 폴백**이며,
 *    장르·템포에 맞는 일반적인 코드 진행(I-V-vi-IV 등 대중적으로 널리 쓰이는
 *    진행 템플릿)으로 연주한다. 특정 곡의 채보를 옮긴 것이 아니다.
 *
 * ── 이전 버전에서 소리가 조잡했던 원인과 수정 ──────────────────────
 *  1) setInterval로 박자를 만들고 ctx.currentTime을 "지금"으로 넘겼다
 *     → JS 타이머 지터가 그대로 박자 흔들림이 됨.
 *     ✅ 25ms마다 깨어나 100ms 앞을 미리 예약하는 lookahead 스케줄러로 교체.
 *        모든 노트가 오디오 클럭 기준의 정확한 시각에 예약된다.
 *  2) 오실레이터를 필터·엔벨로프 없이 그대로 연결
 *     → 삐- 하는 전자음. ✅ ADSR 엔벨로프 + 로우패스 필터 + 디튠 레이어 추가.
 *  3) 공간감이 전혀 없었다 → ✅ 피드백 딜레이 기반 리버브 센드 추가.
 *  4) 모든 파트가 같은 세기로 동시에 울려 뭉갬
 *     → ✅ 파트별 버스 + 킥에 사이드체인 덕킹 + 마스터 컴프레서/리미터.
 */

export type MrStyle = "rock" | "dance" | "acoustic" | "ballad";
export type Progression = "I-V-vi-IV" | "vi-IV-I-V" | "I-vi-IV-V" | "i-VI-III-VII";

export interface MrConfig {
  bpm: number;
  style: MrStyle;
  progression: Progression;
  /** 조성의 으뜸음 주파수(Hz) */
  tonic: number;
}

/* ── 음악 이론 헬퍼 ──────────────────────────────────────────────── */

/** 반음 n개 위로 이조 */
const semi = (freq: number, n: number) => freq * Math.pow(2, n / 12);

/** 진행 템플릿 → 각 마디의 (근음 반음차, 단３화음 여부) */
const PROGRESSION_STEPS: Record<Progression, Array<{ root: number; minor: boolean }>> = {
  "I-V-vi-IV": [
    { root: 0, minor: false },
    { root: 7, minor: false },
    { root: 9, minor: true },
    { root: 5, minor: false },
  ],
  "vi-IV-I-V": [
    { root: 9, minor: true },
    { root: 5, minor: false },
    { root: 0, minor: false },
    { root: 7, minor: false },
  ],
  "I-vi-IV-V": [
    { root: 0, minor: false },
    { root: 9, minor: true },
    { root: 5, minor: false },
    { root: 7, minor: false },
  ],
  "i-VI-III-VII": [
    { root: 0, minor: true },
    { root: 8, minor: false },
    { root: 3, minor: false },
    { root: 10, minor: false },
  ],
};

/** 마디 index → 코드 구성음(3화음 + 7음) 주파수 배열 */
function chordAt(cfg: MrConfig, bar: number): { notes: number[]; bass: number } {
  const steps = PROGRESSION_STEPS[cfg.progression];
  const step = steps[bar % steps.length];
  const root = semi(cfg.tonic, step.root);
  const third = semi(root, step.minor ? 3 : 4);
  const fifth = semi(root, 7);
  const ninth = semi(root, 14); // 색채감을 위한 9음 (한 옥타브 위)
  return {
    notes: [root, third, fifth, ninth],
    // 베이스는 두 옥타브 아래
    bass: root / 4,
  };
}

/* ── 엔진 ────────────────────────────────────────────────────────── */

const LOOKAHEAD_MS = 25; // 스케줄러가 깨어나는 주기
const SCHEDULE_AHEAD_S = 0.12; // 미리 예약해 둘 시간 (초)

/** 파트별 버스 기본 게인 — 덕킹이 되돌아갈 기준값이기도 하다 */
const BUS_GAIN = { drum: 0.9, bass: 0.8, chord: 0.5 } as const;

export class KaraokeAccompanimentEngine {
  private ctx: AudioContext | null = null;

  // 믹서 버스
  private master: GainNode | null = null;
  private drumBus: GainNode | null = null;
  private bassBus: GainNode | null = null;
  private chordBus: GainNode | null = null;
  private reverbSend: GainNode | null = null;

  private noiseBuffer: AudioBuffer | null = null;

  private isRunning = false;
  private volume = 0.7;
  private step = 0; // 16분음표 단위 진행 위치
  private nextNoteTime = 0; // 다음 노트를 예약할 오디오 클럭 시각
  private timerId: ReturnType<typeof setInterval> | null = null;
  private cfg: MrConfig = { bpm: 120, style: "dance", progression: "I-V-vi-IV", tonic: 261.63 };

  /* ── 초기화 ─────────────────────────────────────────────── */

  init() {
    if (typeof window === "undefined" || this.ctx) return;

    const Ctor =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const ctx = new Ctor();
    this.ctx = ctx;

    // 마스터: 컴프레서로 눌러 준 뒤 게인 — 파트가 겹쳐도 클리핑이 나지 않는다
    const comp = ctx.createDynamicsCompressor();
    comp.threshold.setValueAtTime(-14, ctx.currentTime);
    comp.knee.setValueAtTime(24, ctx.currentTime);
    comp.ratio.setValueAtTime(8, ctx.currentTime);
    comp.attack.setValueAtTime(0.004, ctx.currentTime);
    comp.release.setValueAtTime(0.18, ctx.currentTime);

    const master = ctx.createGain();
    master.gain.setValueAtTime(this.volume, ctx.currentTime);

    comp.connect(master);
    master.connect(ctx.destination);
    this.master = master;

    // 파트별 버스
    this.drumBus = ctx.createGain();
    this.bassBus = ctx.createGain();
    this.chordBus = ctx.createGain();
    this.drumBus.gain.value = BUS_GAIN.drum;
    this.bassBus.gain.value = BUS_GAIN.bass;
    this.chordBus.gain.value = BUS_GAIN.chord;
    this.drumBus.connect(comp);
    this.bassBus.connect(comp);
    this.chordBus.connect(comp);

    // 간이 리버브: 피드백 딜레이 2개를 병렬로 — 임펄스 파일 없이 공간감을 만든다
    const send = ctx.createGain();
    send.gain.value = 0.32;
    this.reverbSend = send;

    [0.037, 0.053].forEach((delayTime, i) => {
      const delay = ctx.createDelay(1.0);
      delay.delayTime.value = delayTime;
      const fb = ctx.createGain();
      fb.gain.value = 0.55;
      const damp = ctx.createBiquadFilter();
      damp.type = "lowpass";
      damp.frequency.value = 3200; // 잔향의 고음을 깎아 자연스럽게
      const wet = ctx.createGain();
      wet.gain.value = i === 0 ? 0.5 : 0.36;

      send.connect(delay);
      delay.connect(damp);
      damp.connect(fb);
      fb.connect(delay); // 피드백 루프
      damp.connect(wet);
      wet.connect(comp);
    });

    // 드럼용 화이트노이즈 버퍼 (매 타격마다 새로 만들지 않고 재사용)
    const len = Math.floor(ctx.sampleRate * 0.5);
    const buf = ctx.createBuffer(1, len, ctx.sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < len; i++) data[i] = Math.random() * 2 - 1;
    this.noiseBuffer = buf;
  }

  setVolume(vol: number) {
    this.volume = Math.max(0, Math.min(1, vol));
    if (this.master && this.ctx) {
      // 갑자기 바꾸면 '툭' 소리가 나므로 짧게 램프
      this.master.gain.linearRampToValueAtTime(this.volume, this.ctx.currentTime + 0.05);
    }
  }

  get running() {
    return this.isRunning;
  }

  /* ── 재생 제어 ───────────────────────────────────────────── */

  start(cfg: MrConfig) {
    this.init();
    if (!this.ctx) return;
    if (this.ctx.state === "suspended") void this.ctx.resume();

    this.stop();
    this.cfg = cfg;
    this.isRunning = true;
    this.step = 0;
    this.nextNoteTime = this.ctx.currentTime + 0.08;

    this.timerId = setInterval(() => this.scheduler(), LOOKAHEAD_MS);
  }

  stop() {
    this.isRunning = false;
    if (this.timerId) {
      clearInterval(this.timerId);
      this.timerId = null;
    }
  }

  /** AudioContext까지 완전히 정리 (컴포넌트 언마운트 시) */
  dispose() {
    this.stop();
    if (this.ctx) {
      void this.ctx.close();
      this.ctx = null;
      this.master = this.drumBus = this.bassBus = this.chordBus = this.reverbSend = null;
      this.noiseBuffer = null;
    }
  }

  /* ── lookahead 스케줄러 ──────────────────────────────────── */

  private scheduler() {
    if (!this.isRunning || !this.ctx) return;

    const secondsPer16th = 60 / this.cfg.bpm / 4;

    while (this.nextNoteTime < this.ctx.currentTime + SCHEDULE_AHEAD_S) {
      this.scheduleStep(this.step, this.nextNoteTime, secondsPer16th);

      // 어쿠스틱(셔플) 스타일은 앞 16분음표를 길게, 뒤를 짧게 잡아 스윙감을 만든다
      const swing = this.cfg.style === "acoustic" ? 0.22 : 0;
      this.nextNoteTime +=
        this.step % 2 === 0 ? secondsPer16th * (1 + swing) : secondsPer16th * (1 - swing);

      this.step = (this.step + 1) % 64; // 4마디 루프
    }
  }

  /** 한 개의 16분음표 위치에서 울릴 파트들을 예약 */
  private scheduleStep(step: number, time: number, sec16: number) {
    const bar = Math.floor(step / 16) % 4;
    const beat = Math.floor((step % 16) / 4);
    const sub = step % 4;
    const { notes, bass } = chordAt(this.cfg, bar);
    const style = this.cfg.style;

    /* 드럼 */
    const kickHere =
      style === "dance"
        ? sub === 0 // 4-on-the-floor
        : (beat === 0 && sub === 0) || (beat === 2 && sub === 0) || (style === "rock" && beat === 1 && sub === 2);
    if (kickHere) {
      this.kick(time);
      this.duck(time); // 킥에 맞춰 코드/베이스를 잠깐 눌러 준다 (사이드체인)
    }
    if ((beat === 1 || beat === 3) && sub === 0) this.snare(time, style);
    if (style === "ballad" ? sub === 0 : sub % 2 === 0) {
      this.hat(time, sub === 0 ? 0.09 : 0.05, style === "dance" && sub === 2);
    }

    /* 베이스 — 스타일에 따라 밀도를 바꾼다 */
    const bassHere =
      style === "dance"
        ? sub === 0 || sub === 2
        : style === "rock"
        ? sub === 0 || (beat % 2 === 1 && sub === 2)
        : sub === 0 && beat % 2 === 0;
    if (bassHere) {
      const isOff = sub !== 0;
      this.bass(isOff ? bass * 2 : bass, time, sec16 * (style === "ballad" ? 8 : 3.4), style);
    }

    /* 코드 */
    if (style === "rock" && sub === 0) {
      // 록: 8분음표 스트로크로 리듬감 있게
      this.chord(notes, time, sec16 * 1.8, style, beat === 0 ? 0.9 : 0.62);
    } else if (style === "dance" && (sub === 2 || (beat === 0 && sub === 0))) {
      // 댄스: 엇박 스탭 코드
      this.chord(notes, time, sec16 * 1.4, style, 0.7);
    } else if ((style === "acoustic" || style === "ballad") && beat % 2 === 0 && sub === 0) {
      // 어쿠스틱/발라드: 길게 깔아 주는 패드
      this.chord(notes, time, sec16 * 7.5, style, 0.8);
    }

    /* 마디 첫 박에 아르페지오 한 알갱이 — 밋밋함을 덜어 준다 */
    if (sub === 0 && beat === 3) {
      this.pluck(notes[(bar + 2) % notes.length] * 2, time, sec16 * 2);
    }
  }

  /* ── 악기 합성 ───────────────────────────────────────────── */

  /** 킥에 맞춰 코드/베이스 버스를 순간적으로 눌렀다 되돌린다 */
  private duck(time: number) {
    if (!this.chordBus || !this.bassBus) return;
    const targets: Array<[GainNode, number]> = [
      [this.chordBus, BUS_GAIN.chord],
      [this.bassBus, BUS_GAIN.bass],
    ];
    targets.forEach(([bus, base]) => {
      bus.gain.cancelScheduledValues(time);
      bus.gain.setValueAtTime(base * 0.55, time);
      bus.gain.linearRampToValueAtTime(base, time + 0.16);
    });
  }

  private kick(time: number) {
    const ctx = this.ctx;
    if (!ctx || !this.drumBus) return;

    // 사인 스윕 = 몸통
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(150, time);
    osc.frequency.exponentialRampToValueAtTime(42, time + 0.09);
    gain.gain.setValueAtTime(0.0001, time);
    gain.gain.exponentialRampToValueAtTime(0.95, time + 0.004); // 짧은 어택
    gain.gain.exponentialRampToValueAtTime(0.0001, time + 0.28);
    osc.connect(gain).connect(this.drumBus);
    osc.start(time);
    osc.stop(time + 0.3);

    // 클릭 = 어택감 (스피커가 작아도 킥이 들리게)
    if (this.noiseBuffer) {
      const n = ctx.createBufferSource();
      n.buffer = this.noiseBuffer;
      const hp = ctx.createBiquadFilter();
      hp.type = "bandpass";
      hp.frequency.value = 1800;
      const g = ctx.createGain();
      g.gain.setValueAtTime(0.18, time);
      g.gain.exponentialRampToValueAtTime(0.0001, time + 0.018);
      n.connect(hp).connect(g).connect(this.drumBus);
      n.start(time);
      n.stop(time + 0.03);
    }
  }

  private snare(time: number, style: MrStyle) {
    const ctx = this.ctx;
    if (!ctx || !this.drumBus || !this.noiseBuffer || !this.reverbSend) return;

    const noise = ctx.createBufferSource();
    noise.buffer = this.noiseBuffer;
    const bp = ctx.createBiquadFilter();
    bp.type = "bandpass";
    bp.frequency.value = style === "rock" ? 2200 : 1700;
    bp.Q.value = 0.7;
    const g = ctx.createGain();
    const dur = style === "ballad" ? 0.22 : 0.16;
    g.gain.setValueAtTime(0.0001, time);
    g.gain.exponentialRampToValueAtTime(style === "rock" ? 0.5 : 0.34, time + 0.003);
    g.gain.exponentialRampToValueAtTime(0.0001, time + dur);
    noise.connect(bp).connect(g);
    g.connect(this.drumBus);
    g.connect(this.reverbSend); // 스네어만 잔향을 보내 공간감을 만든다
    noise.start(time);
    noise.stop(time + dur + 0.02);

    // 통 울림
    const osc = ctx.createOscillator();
    const og = ctx.createGain();
    osc.type = "triangle";
    osc.frequency.setValueAtTime(210, time);
    osc.frequency.exponentialRampToValueAtTime(120, time + 0.07);
    og.gain.setValueAtTime(0.22, time);
    og.gain.exponentialRampToValueAtTime(0.0001, time + 0.09);
    osc.connect(og).connect(this.drumBus);
    osc.start(time);
    osc.stop(time + 0.1);
  }

  private hat(time: number, vol: number, open: boolean) {
    const ctx = this.ctx;
    if (!ctx || !this.drumBus || !this.noiseBuffer) return;
    const n = ctx.createBufferSource();
    n.buffer = this.noiseBuffer;
    const hp = ctx.createBiquadFilter();
    hp.type = "highpass";
    hp.frequency.value = 8200;
    const g = ctx.createGain();
    const dur = open ? 0.13 : 0.035;
    g.gain.setValueAtTime(vol, time);
    g.gain.exponentialRampToValueAtTime(0.0001, time + dur);
    n.connect(hp).connect(g).connect(this.drumBus);
    n.start(time);
    n.stop(time + dur + 0.01);
  }

  private bass(freq: number, time: number, dur: number, style: MrStyle) {
    const ctx = this.ctx;
    if (!ctx || !this.bassBus) return;

    // 톱니파를 로우패스로 깎아 만드는 신스 베이스 — 사인/삼각파보다 훨씬 두툼하다
    const osc = ctx.createOscillator();
    osc.type = style === "acoustic" ? "triangle" : "sawtooth";
    osc.frequency.setValueAtTime(freq, time);

    const lp = ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.Q.value = 6;
    // 필터 엔벨로프 — 뜯는 느낌(pluck)을 만든다
    lp.frequency.setValueAtTime(Math.min(4200, freq * 14), time);
    lp.frequency.exponentialRampToValueAtTime(Math.max(90, freq * 2.4), time + Math.min(0.25, dur));

    const g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, time);
    g.gain.exponentialRampToValueAtTime(0.5, time + 0.012);
    g.gain.exponentialRampToValueAtTime(0.0001, time + dur);

    osc.connect(lp).connect(g).connect(this.bassBus);
    osc.start(time);
    osc.stop(time + dur + 0.03);
  }

  private chord(notes: number[], time: number, dur: number, style: MrStyle, vel: number) {
    const ctx = this.ctx;
    if (!ctx || !this.chordBus || !this.reverbSend) return;

    const wave: OscillatorType =
      style === "acoustic" ? "triangle" : style === "rock" ? "sawtooth" : "square";

    notes.forEach((freq, i) => {
      // 한 음마다 살짝 디튠한 오실레이터 2개 → 코러스처럼 두꺼워진다
      [-5, 5].forEach((cents) => {
        const osc = ctx.createOscillator();
        osc.type = wave;
        osc.frequency.setValueAtTime(freq, time);
        osc.detune.setValueAtTime(cents, time);

        const lp = ctx.createBiquadFilter();
        lp.type = "lowpass";
        lp.frequency.setValueAtTime(style === "rock" ? 2600 : 1900, time);
        lp.Q.value = 0.8;

        const g = ctx.createGain();
        // 위쪽 음일수록 작게 — 저음이 뭉치지 않게
        const peak = (0.085 * vel) / (1 + i * 0.45);
        const attack = style === "rock" ? 0.006 : 0.06;
        g.gain.setValueAtTime(0.0001, time);
        g.gain.exponentialRampToValueAtTime(peak, time + attack);
        g.gain.exponentialRampToValueAtTime(peak * 0.6, time + dur * 0.5); // 서스테인
        g.gain.exponentialRampToValueAtTime(0.0001, time + dur);

        osc.connect(lp).connect(g);
        g.connect(this.chordBus!);
        g.connect(this.reverbSend!);
        osc.start(time);
        osc.stop(time + dur + 0.05);
      });
    });
  }

  private pluck(freq: number, time: number, dur: number) {
    const ctx = this.ctx;
    if (!ctx || !this.chordBus || !this.reverbSend) return;
    const osc = ctx.createOscillator();
    osc.type = "triangle";
    osc.frequency.setValueAtTime(freq, time);
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, time);
    g.gain.exponentialRampToValueAtTime(0.11, time + 0.008);
    g.gain.exponentialRampToValueAtTime(0.0001, time + dur);
    osc.connect(g);
    g.connect(this.chordBus);
    g.connect(this.reverbSend);
    osc.start(time);
    osc.stop(time + dur + 0.02);
  }
}
