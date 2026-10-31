// 실습 영상의 도해 두 장 (1920x896 SVG). data-k 가 장면 단계에서 켜고 끄는 열쇠다.
(function () {
  "use strict";
  const node = (k, x, y, w, h, t, s, m) =>
    `<g class="node" data-k="${k}"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="18"/>` +
    `<text class="t" x="${x + 26}" y="${y + 50}">${t}</text>` +
    (s ? `<text class="s" x="${x + 26}" y="${y + 88}">${s}</text>` : "") +
    (m ? `<text class="m" x="${x + 26}" y="${y + 120}">${m}</text>` : "") + `</g>`;
  const edge = (id, k, d, lbl, lx, ly, anchor = "middle") =>
    `<path id="${id}" class="edge" data-k="${k}" d="${d}" marker-end="url(#ar)"/>` +
    `<text class="elbl" data-k="${k}" x="${lx}" y="${ly}" text-anchor="${anchor}">${lbl}</text>` +
    `<circle class="pulse" r="9" data-path="${id}" style="display:none"/>`;
  const area = (k, x, y, w, h, label) =>
    `<g data-k="${k}"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="26" fill="none" stroke="#3A3F49" stroke-width="2" stroke-dasharray="10 8"/>` +
    `<text x="${x + 22}" y="${y + 34}" style="font-size:22px;font-weight:800;fill:#6E747E">${label}</text></g>`;

  const flow = `<svg class="dg" viewBox="0 0 1920 896" xmlns="http://www.w3.org/2000/svg">
    <defs><marker id="ar" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#8A909A"/></marker></defs>
    ${area("role_pi", 36, 40, 930, 760, "라즈베리파이 담당 · 1편")}
    ${area("role_be", 1000, 40, 520, 560, "백엔드 담당 · 2편")}
    ${area("role_fe", 1550, 40, 345, 330, "프론트 담당 · 2편")}
    ${node("door", 70, 110, 300, 150, "🚪 문 + 자석", "문틀에 리드 스위치", "door_sensor_1")}
    ${node("pi", 530, 110, 400, 150, "🍓 라즈베리파이", "pi/main.py", "GPIO23 읽기 · GPIO25 출력")}
    ${node("be", 1040, 110, 440, 150, "🖥 백엔드 (FastAPI)", "기기 목록 · 목표 상태 보관", "/api/v1/devices/…")}
    ${node("rule", 1040, 400, 440, 160, "⚖ 규칙", "잠금 + 문 열림 → 부저 on", "check_door_alarm()")}
    ${node("fe", 1580, 110, 290, 220, "💻 관리자 화면", "/admin", "문 센서 · 부저 표시")}
    ${node("buzzer", 70, 590, 300, 150, "🔔 경고 부저", "액티브 부저 모듈", "buzzer_1")}
    ${edge("p_door", "e_door", "M370,185 L530,185", "자석이 떨어짐", 450, 168)}
    ${edge("p_report", "e_report", "M930,160 L1040,160", "① 문 상태 보고", 985, 140)}
    ${edge("p_rule", "e_rule", "M1260,260 L1260,400", "② 규칙 판단", 1280, 340, "start")}
    ${edge("p_poll", "e_poll", "M1040,225 L930,225", "③ 부저 지시 (폴링)", 985, 262)}
    ${edge("p_buzz", "e_buzz", "M730,260 L730,665 L370,665", "④ GPIO25 → 삐-", 748, 470, "start")}
    ${edge("p_ws", "e_ws", "M1480,185 L1580,185", "⑤ 실시간", 1530, 168)}
  </svg>`;

  // ── 40핀 헤더 배선도 ──
  const PIN = {
    1: "3V3", 2: "5V", 3: "GPIO2", 4: "5V", 5: "GPIO3", 6: "GND", 7: "GPIO4", 8: "GPIO14", 9: "GND", 10: "GPIO15",
    11: "GPIO17", 12: "GPIO18", 13: "GPIO27", 14: "GND", 15: "GPIO22", 16: "GPIO23", 17: "3V3", 18: "GPIO24", 19: "GPIO10", 20: "GND",
    21: "GPIO9", 22: "GPIO25", 23: "GPIO11", 24: "GPIO8", 25: "GND", 26: "GPIO7", 27: "ID_SD", 28: "ID_SC", 29: "GPIO5", 30: "GND",
    31: "GPIO6", 32: "GPIO12", 33: "GPIO13", 34: "GND", 35: "GPIO19", 36: "GPIO16", 37: "GPIO26", 38: "GPIO20", 39: "GND", 40: "GPIO21",
  };
  // 부스가 이미 쓰는 핀 (booth_pins.py)
  const USED = { 11: "도어락", 13: "전원 릴레이", 15: "LED", 18: "PIR", 29: "키패드", 31: "키패드", 33: "키패드", 35: "키패드", 37: "키패드", 36: "키패드", 38: "키패드", 40: "키패드" };
  const HX = 860, HY = 70, PITCH = 38;
  const px = (n) => (n % 2 ? HX : HX + 46);
  const py = (n) => HY + 26 + Math.floor((n - 1) / 2) * PITCH;
  let pins = "";
  for (let n = 1; n <= 40; n++) {
    const role = PIN[n];
    const cls = role === "GND" ? "gnd" : role === "3V3" ? "v33" : role === "5V" ? "v5" : "gpio";
    const keys = [`p${n}`];
    if (USED[n]) keys.push("used");
    pins += `<rect class="pin ${cls}" data-k="${keys.join(" ")}" x="${px(n) - 14}" y="${py(n) - 14}" width="28" height="28" rx="5"/>`;
    const lx = n % 2 ? HX - 26 : HX + 72, anchor = n % 2 ? "end" : "start";
    const used = USED[n] ? ` · ${USED[n]}` : "";
    pins += `<text class="plbl" data-k="${keys.join(" ")}" x="${lx}" y="${py(n) - 5}" text-anchor="${anchor}">${n}  ${role}${used}</text>`;
  }
  const W = (k, color, d) => `<path class="wire" data-k="${k}" stroke="${color}" d="${d}"/>`;
  const reedY = 250, buzY = 560;
  const wiring = `<svg class="dg" viewBox="0 0 1920 896" xmlns="http://www.w3.org/2000/svg">
    <rect class="board" x="${HX - 300}" y="${HY - 30}" width="${46 + 600}" height="${20 * PITCH + 50}" rx="22"/>
    <text x="${HX - 270}" y="${HY + 4}" style="font-size:22px;font-weight:800;fill:#9FD3B4">라즈베리파이 5 · 40핀 헤더</text>
    <rect x="${HX - 24}" y="${HY + 4}" width="${46 + 48}" height="${20 * PITCH + 4}" rx="8" fill="#0B1F14" stroke="#2F6B47"/>
    ${pins}
    <g class="part" data-k="reed">
      <rect class="part" data-k="reed" x="1380" y="${reedY - 70}" width="420" height="150" rx="18"/>
      <text x="1408" y="${reedY - 22}" style="font-size:30px;font-weight:800">🧲 리드 스위치</text>
      <text x="1408" y="${reedY + 18}" style="font-size:21px;fill:#AEB2BA">문틀에 붙이고, 자석은 문에</text>
      <text x="1408" y="${reedY + 52}" style="font-size:20px;fill:#E9BC5E;font-family:D2Coding">선 2가닥 · 극성 없음</text>
    </g>
    <g class="part" data-k="buzzer">
      <rect class="part" data-k="buzzer" x="1380" y="${buzY - 60}" width="420" height="230" rx="18"/>
      <text x="1408" y="${buzY - 12}" style="font-size:30px;font-weight:800">🔔 액티브 부저 모듈</text>
      <text x="1408" y="${buzY + 26}" style="font-size:21px;fill:#AEB2BA">전원만 주면 스스로 삐- 소리</text>
      <text x="1408" y="${buzY + 72}" style="font-size:20px;fill:#F2CC60;font-family:D2Coding">S   신호</text>
      <text x="1408" y="${buzY + 108}" style="font-size:20px;fill:#FF7B72;font-family:D2Coding">VCC 전원 3.3V</text>
      <text x="1408" y="${buzY + 144}" style="font-size:20px;fill:#9AA0A6;font-family:D2Coding">GND 접지</text>
    </g>
    ${W("reed w_reed", "#F2CC60", `M${px(16) + 14},${py(16)} L1200,${py(16)} L1200,${reedY - 10} L1380,${reedY - 10}`)}
    ${W("reed w_reed", "#9AA0A6", `M${px(14) + 14},${py(14)} L1160,${py(14)} L1160,${reedY + 30} L1380,${reedY + 30}`)}
    ${W("buzzer w_buz", "#F2CC60", `M${px(22) + 14},${py(22)} L1240,${py(22)} L1240,${buzY + 66} L1380,${buzY + 66}`)}
    ${W("buzzer w_buz", "#9AA0A6", `M${px(20) + 14},${py(20)} L1280,${py(20)} L1280,${buzY + 138} L1380,${buzY + 138}`)}
    ${W("buzzer w_buz", "#FF7B72", `M${px(17) - 14},${py(17)} L${HX - 300 + 20},${py(17)} L${HX - 300 + 20},${HY + 20 * PITCH + 40} L1320,${HY + 20 * PITCH + 40} L1320,${buzY + 102} L1380,${buzY + 102}`)}
    <text class="note" data-k="legend" x="80" y="${HY + 20 * PITCH + 90}">노랑 = GPIO 신호 · 회색 = GND · 빨강 = 3.3V   (번호는 물리 핀 번호, 코드에는 BCM 번호를 씁니다)</text>
  </svg>`;

  window.DIAGRAMS = { flow, wiring };
})();
