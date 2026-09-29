# 하나증권 리서치 트래킹 에이전트

하나증권 그룹포탈(hanaw.com)에 매일 올라오는 산업분석·기업분석·채권분석
리포트를 수집해, 개별 리포트 요약이 아니라 산업 단위로 묶은 "이번 주 이
산업은 이렇게 흘러가고 있다" 수준의 브리핑을 만드는 것이 목표.

## 설계 원칙
- 상시 서버 없음: GitHub Actions 스케줄 트리거로 배치 실행, 상태는 전부 git
  commit으로 저장한다.
- PDF 원문은 절대 커밋하지 않는다: 다운로드 → 텍스트 추출(메모리에서만) →
  즉시 폐기. 커밋 대상은 구조화된 텍스트/JSON뿐이다.
- 개별 리포트(`report_type: individual`)와 데일리 종합물(`daily_series`,
  예: Hana Guru Eye)을 구분해서 처리한다 — 후자는 이미 그날의 개별 이슈를
  요약해서 담고 있어, 섞어서 산업 브리핑 재료로 쓰면 같은 이슈가 이중
  카운트된다.
- 소스 확장을 염두에 두고 `scripts/collectors/base.py`의 `ReportCollector`
  인터페이스로 어댑터를 분리한다. 지금 실제로 구현/실행하는 소스는
  하나증권(`hana.py`) 하나뿐이다.

## 현재 상태
수집(collect) + PDF 텍스트 추출(extract)이 동작한다. GitHub Actions가 평일
KST 09/12/18시에 하나증권 전체 리서치 피드를 훑어 신규 리포트만 저장하고
커밋한다. 요약/태깅/브리핑 등 가공 단계는 이 저장소 밖에서 처리한다.

수집 결과: `data/reports/{발행일}/hana_{bbsSeq}.json`
```
report_id, report_type(individual|daily_series), title, analyst,
published_date, published_time, category, breadcrumb, preview_text,
pdf_url, pdf_filename, source_url, collected_at, pdf_text, (pdf_error)
```
PDF 추출에 실패한 리포트는 `pdf_error`와 함께 저장되고, seen 인덱스에
들어가지 않으므로 다음 실행에서 재시도된다.

## 유의사항
- 대상 사이트의 robots.txt는 Googlebot/Yeti 외 자동화 접근을 Disallow 한다.
  요청 간 1.5초 딜레이를 두고 있으며, 정기 실행을 멈추려면 워크플로의
  `schedule:` 블록을 주석 처리한다.
- `pdf_text`에는 리포트 원문 텍스트가 들어간다. 저장소가 public이면
  원문이 공개 재배포되므로 저장소를 private으로 두는 것을 권장한다.

## 디렉터리 구조
```
skills/                 각 파이프라인 단계의 SKILL.md (언제/입력/처리절차/출력형식/주의사항)
scripts/
  collectors/base.py    공통 수집기 인터페이스
  collectors/hana.py    하나증권 어댑터 (전체 피드 list.cmd 파싱)
  pdf_extract.py        PDF 바이트 -> 텍스트 (메모리 전용)
  report_index.py       seen_reports.json 기반 중복 방지
  run_pipeline.py        collect -> extract 오케스트레이션
data/
  index/seen_reports.json   수집 완료 report_id 마스터 인덱스
  reports/{date}/{id}.json  리포트별 메타데이터 + PDF 추출 텍스트 (date = 발행일)
  industries/{industry}/    산업별 이력 + 주간 브리핑
digest/{date}.md         오늘의 다이제스트
```

## 로컬 실행
```
pip install -r requirements.txt
python scripts/run_pipeline.py --max-pages 3            # 최근 30건까지
python scripts/run_pipeline.py --max-pages 3 --skip-pdf # 메타데이터만
```
첫 실행은 `--max-pages` 만큼 과거로 거슬러 올라가고, 이후 실행은 이미
본 리포트만 있는 페이지가 나오면 멈춘다.
