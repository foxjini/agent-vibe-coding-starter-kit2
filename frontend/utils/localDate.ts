/**
 * 이 기기의 달력 날짜 (YYYY-MM-DD)
 *
 * `new Date().toISOString()` 은 **UTC** 날짜다. 한국에서는 오전 9시 전까지
 * 어제 날짜가 나와서, 그 시간에는 "당일 예약 불가" 검사가 하루씩 밀렸다.
 * 날짜를 비교할 때는 이 함수를 쓴다.
 */
export function localDateString(offsetDays = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}
