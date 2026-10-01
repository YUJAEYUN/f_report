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
   이어서 요약과 구분되는 `insight`를 작성한다. 관점은 **리서치 독자의 판단 보조**로
   고정하고, 다음 세 질문에만 답한다.
   - `change`: 기존 전제와 비교해 무엇이 달라졌는가?
   - `implication`: 그 변화가 기업·산업·시장 흐름을 이해하는 데 왜 중요한가?
   - `watch_points`: 이 해석이 이어지는지 확인할 관찰 지표나 사건은 무엇인가? (1~3개)
   원문에 비교 기준이 없으면 `change`에서 현재 리포트가 강조한 변화를 쓰되, 과거 사실을
   추정하지 않는다. `implication`은 매수·매도나 수익률 예측이 아니라 원문의 논리를 한 단계
   해석한 문장으로 쓴다.
2. **daily_series**: 전체를 하나로 요약하지 않는다. 본문에 이미 bullet로
   나열된 개별 이슈들을 그대로 항목별 리스트로 보존한다(각 bullet의 종목/이슈명
   + 한 줄). 이 결과는 산업 브리핑 합성 재료로 넘기지 않고, build-digest의
   "오늘의 데일리 코멘트" 섹션 전용으로만 쓴다.
3. 원문 `pdf_text`는 지우지 않고 남긴다 — 프롬프트나 산업 분류 체계를 바꿨을 때
   원문 기준으로 다시 요약/태깅할 수 있어야 한다. 요약 결과는 같은 레코드에
   `summary`와 `insight`(+ individual은 `industry_tags`, 공통으로 `summarized_at`)로 덧붙인다.
   daily_series는 `summary`, individual은 `summary`와 `insight`가 모두 있어야 가공 완료다.

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
individual은 같은 최상위 객체에 다음 형태의 `insight`를 추가한다.
```json
{
  "insight": {
    "change": "...",
    "implication": "...",
    "watch_points": ["..."]
  }
}
```
daily_series는 `summary.items: [{"topic": "...", "note": "..."}]` 형태로 대체.

## 주의사항
- 원문을 왜곡하지 않는다: 리포트에 없는 숫자/의견을 만들어내지 않는다.
  불확실하면 null/빈 배열로 두고 넘어간다.
- 인사이트는 반드시 원문과 요약에서 근거를 찾을 수 있어야 한다. 다른 리포트, 주가 또는
  최신 뉴스를 알고 있다고 가정하지 않고, 투자 추천처럼 표현하지 않는다.
- individual과 daily_series를 같은 스키마로 억지로 맞추지 않는다 — 이후
  tag-industry, synthesize-industry-brief 단계에서 report_type으로 분기 처리한다.
