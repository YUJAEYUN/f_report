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

## 현재 상태 (중요)
`scripts/collectors/hana.py`는 아직 실제 파싱 로직이 없다. 이 세션의
네트워크 egress 정책이 `www.hanaw.com`으로의 아웃바운드를 차단하고 있어
list.cmd 페이지의 실제 DOM/응답을 라이브로 확인하지 못했다 (robots.txt
얘기와는 별개로, 이 실행 환경 자체의 네트워크 정책 문제). `hana.py`
상단 docstring에 확인이 필요한 항목과 확인 방법이 정리되어 있다.

## 사내 정책 관련 유의사항
대상 사이트의 robots.txt가 자동화 접근을 명시적으로 막고 있다. 지금 단계
(구조 설계, 개인 테스트)는 진행 가능하지만, 실제 정기 스케줄링(운영 배포)에
들어가기 전에는 반드시 사내 정책 확인을 거칠 것. `.github/workflows/daily-pipeline.yml`의
`schedule:` 트리거는 그때까지 주석 처리해둔다.

## 디렉터리 구조
```
skills/                 각 파이프라인 단계의 SKILL.md (언제/입력/처리절차/출력형식/주의사항)
scripts/
  collectors/base.py    공통 수집기 인터페이스
  collectors/hana.py    하나증권 어댑터 (파싱 로직 라이브 검증 대기)
  pdf_extract.py        PDF 바이트 -> 텍스트 (메모리 전용)
  report_index.py       seen_reports.json 기반 중복 방지
  run_pipeline.py        collect -> extract 오케스트레이션
data/
  index/seen_reports.json   수집 완료 report_id 마스터 인덱스
  reports/{date}/{id}.json  리포트별 구조화 데이터 (원문 텍스트 미보관 원칙)
  industries/{industry}/    산업별 이력 + 주간 브리핑
digest/{date}.md         오늘의 다이제스트
```

## 로컬 실행
```
pip install -r requirements.txt
python scripts/run_pipeline.py --max-pages 3
```
`hana.py`가 아직 스텁이라 지금은 신규 리포트 0건으로 정상 종료된다.
