# hardware-swap (Mock → 라즈베리파이 5)

1. Mock 상태에서 모든 기능이 정상 동작함을 먼저 확인한다
2. hardware-integration 스킬을 참고해 `hardware_provider.py`를 작성한다 (gpiozero)
3. 배선은 전원을 끈 상태에서, 교사 입회 하에 연결한다
4. `.env`의 `DEVICE_MODE=hardware`로 전환한다 (다른 파일은 건드리지 않는다)
5. 실기기 동작을 확인한다. 프론트/백엔드 코드를 고쳐야 했다면 Provider 패턴이 깨진
   것이니 되짚어본다
