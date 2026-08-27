# collect-reports

## 언제
GitHub Actions 스케줄 트리거(하루 N회)에서 파이프라인 맨 앞 단계로 실행한다.
사람이 수동으로 "오늘자 리포트 가져와줘"라고 요청했을 때도 동일하게 쓴다.

## 입력
- 소스 이름 (예: `hana`) — `scripts/collectors/`에서 어댑터를 선택하는 데 사용
- `data/index/seen_reports.json` — 이미 수집한 report_id 전체 목록
- `max_pages` — 안전장치용 최대 페이지 수 (무한 루프 방지)

## 처리절차
1. `data/index/seen_reports.json`을 읽어 해당 소스의 가장 최근 `bbs_seq`를 구한다
   (`scripts/report_index.latest_seq_for_source`).
2. 소스별 collector(`ReportCollector` 구현체)의 `iter_recent_reports(max_pages, stop_before_seq)`를
   호출해 신규 리포트만 최신순으로 순회한다.
3. 각 리포트 항목에서 breadcrumb를 근거로 `report_type`을 `individual` /
   `daily_series`로 분류한다. Daily 계열(예: Hana Guru Eye, 하루에 하나)은
   그날의 개별 리포트를 이미 요약해서 담고 있으므로 반드시 구분해서 태깅한다 —
   이후 산업 브리핑 합성에는 `individual`만 재료로 쓰고, `daily_series`는
   다이제스트의 별도 "오늘의 데일리 코멘트" 섹션으로만 사용한다 (섞으면 같은
   이슈가 이중 카운트되어 브리핑이 왜곡됨).
4. 요청 사이 최소 1.5초 딜레이, 정상적인 접근임을 알리는 User-Agent 유지.
5. 새로 발견한 report_id를 모아 `add_seen_ids`로 인덱스에 반영한다.

## 출력형식
`RawReportItem`(또는 이를 dict화한 것) 목록. 필드: `report_id`, `source`,
`bbs_cd`, `bbs_seq`, `report_type`, `title`, `analyst`, `published_date`,
`category`, `breadcrumb`, `preview_text`, `pdf_url`, `pdf_filename`,
`source_url`. 이 단계에서는 PDF 본문 텍스트를 포함하지 않는다 (extract-report의 몫).

## 주의사항
- PDF 파일을 디스크에 저장하지 않는다. 이 skill은 리스트 페이지만 다루고
  PDF 다운로드/텍스트 추출은 하지 않는다.
- 대상 사이트의 robots.txt가 자동화 접근을 명시적으로 막고 있음을 인지한다.
  현재는 사내 직원이 자사 발행 자료를 내부 트래킹 목적으로 개인/구조 검증
  차원에서 다루는 단계다. 실제 정기 스케줄링(운영 배포) 전에는 반드시 사내
  정책 확인을 거칠 것.
- 새 증권사를 추가할 때는 `scripts/collectors/base.py`의 `ReportCollector`
  인터페이스만 구현하면 되고, 이 skill의 절차는 바뀌지 않아야 한다.
- 요청이 반복 차단되거나 응답 패턴이 바뀌면 즉시 중단하고 사람에게 보고한다
  (무리하게 우회 시도하지 않는다).
