# 팀별 배치표 예시 (pi/examples/)

우리 팀 하드웨어에 맞는 파일을 골라 **`pi/slot_map.py`로 복사**한 뒤,
핀 번호만 실제 배선에 맞게 고치면 됩니다.

```bash
cd pi
cp examples/slot_map_classroom.py slot_map.py   # 자기 팀 파일로
python daemon.py --check                        # 핀 충돌·오타 확인
python daemon.py                                # 실행
```

| 파일 | 팀 | 부품 |
|---|---|---|
| `slot_map_wakeup.py` | wakeup | 피에조 부저, 기상 확인 버튼 |
| `slot_map_classroom.py` | classroom | 서보(자동문), 좌석 LED, 네오픽셀, 부저, 릴레이 |
| `slot_map_study.py` | study | RGB 스탠드, 진동모터 2개, 릴레이, 터치 입력 |
| `slot_map_subway.py` | subway | 혼잡도 단계 LED, 컨베이어 모터, 좌석 압력센서 |

> 핀 번호는 **BCM 기준**(보드의 물리 핀 번호가 아닙니다)이고, 예시일 뿐입니다.
> 실제로 어디에 꽂았는지 확인하고 고쳐 주세요. `python daemon.py --check`가
> 핀 중복이나 오타를 실행 전에 잡아 줍니다.

부품을 더 붙이거나 떼는 방법, 쓸 수 있는 드라이버 목록은
[docs/부록F](../../docs/부록F-IoT-개발-플랫폼-키트-규약.md) 8장을 보세요.
