# summarize-report

## 언제
extract-report가 `pdf_text`(또는 preview_text만 있는 경우 그것)를 넘긴 직후,
tag-industry보다 먼저 실행한다. `report_type`이 `individual`인지 `daily_series`인지에
따라 처리 방식이 달라진다 (아래 처리절차 참고).

## 입력
- `RawReportItem` + `pdf_text`
- `report_type` (individual / daily_series)

## 처리절차
1. **individual**: 본문에서 다음을 추출한다 — 한 줄 요약(one_liner), 투자의견
   (rating)과 직전 대비 변경 여부(rating_change: 유지/상향/하향/신규),
   목표주가(target_price, 없으면 null), 핵심 포인트 3~5개(key_points), 리스크
   요인(risk_factors). 종목명이 명시되면 ticker(예: `096770.KS`)도 뽑는다.
2. **daily_series**: 전체를 하나로 요약하지 않는다. 본문에 이미 bullet로
   나열된 개별 이슈들을 그대로 항목별 리스트로 보존한다(각 bullet의 종목/이슈명
   + 한 줄). 이 결과는 산업 브리핑 합성 재료로 넘기지 않고, build-digest의
   "오늘의 데일리 코멘트" 섹션 전용으로만 쓴다.
3. 원문 `pdf_text`는 요약 생성 후 결과 레코드에서 제거한다 — 커밋되는
   `data/reports/{date}/{report_id}.json`에는 구조화된 요약만 남는다.

## 출력형식
데이터 스키마의 `summary` 객체:
```json
{
  "one_liner": "...",
  "rating": "매수",
  "rating_change": "유지",
  "target_price": null,
  "key_points": ["..."],
  "risk_factors": ["..."]
}
```
daily_series는 `summary.items: [{"topic": "...", "note": "..."}]` 형태로 대체.

## 주의사항
- 원문을 왜곡하지 않는다: 리포트에 없는 숫자/의견을 만들어내지 않는다.
  불확실하면 null/빈 배열로 두고 넘어간다.
- individual과 daily_series를 같은 스키마로 억지로 맞추지 않는다 — 이후
  tag-industry, synthesize-industry-brief 단계에서 report_type으로 분기 처리한다.
