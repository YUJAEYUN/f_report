# tag-industry

## 언제
summarize-report 직후, `report_type: individual` 리포트에 대해서만 실행한다
(daily_series는 이미 종합물이라 산업 태깅 대상에서 제외 — build-digest가 별도 처리).

## 입력
- 요약된 리포트 레코드 (`title`, `category`, `summary`, `ticker` 등)
- `data/industries/`에 이미 존재하는 산업 디렉터리 목록 (기존 산업명과의 일관성 유지용)

## 처리절차
1. 제목/카테고리(breadcrumb)/요약 내용을 근거로 `industry_tags`를 1~3개
   부여한다. 종목이 여러 산업에 걸치면(예: 배터리 소재 기업) 복수 태깅을 허용한다.
2. 기존에 `data/industries/{industry}/`로 존재하는 산업명이 있으면 새 이름을
   만들지 말고 그것을 재사용한다 (예: "2차전지"와 "배터리"를 따로 만들지 않기).
   완전히 새로운 산업이면 새 디렉터리를 만들 근거를 남긴다.
3. 태깅 결과를 리포트 레코드의 `industry_tags` 필드에 반영하고,
   해당 산업들의 `data/industries/{industry}/history.json`에 이 report_id를 추가한다.

## 출력형식
- 갱신된 리포트 레코드 (`industry_tags: ["정유", "배터리"]`)
- `data/industries/{industry}/history.json`: `{"report_ids": ["hana_1288559", ...]}`

## 주의사항
- 산업 분류 체계가 세션마다 흔들리면 이후 브리핑 합성이 파편화된다 — 태깅 전에
  반드시 기존 `data/industries/` 목록을 먼저 확인한다.
- 채권분석처럼 특정 기업 산업보다 거시/금리 성격이 강한 리포트는 "채권/금리"
  같은 별도 카테고리로 두고, 억지로 개별 산업에 끼워 맞추지 않는다.
