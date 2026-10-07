# 하나증권 리서치 트래킹 에이전트

## 목적
리서치 리포트를 직접 다 읽지 않아도 시장과 산업의 흐름을 쉽게 따라갈 수 있게
해주는 **개인용 트래킹 도구**.

하나증권 그룹포탈(hanaw.com)에 매일 올라오는 리서치를 자동으로 모아 요약하고,
산업·테마별로 묶어 **일 단위·주 단위 인사이트**로 정리한다. 대시보드에서
한눈에 훑어보고, 관심 가는 건 요약 → 원문 순서로 깊이 들어갈 수 있게 한다.
투자 판단용이 아니라 **흐름을 이해하고 공부하는 용도**이므로, 숫자·목표주가보다
"왜 그렇게 보는지"의 논리와 그 변화를 우선한다.

### 로드맵
1. 수집·원문 추출 (완료)
2. 요약 + 분류(desk / 산업 / 테마) (완료)
3. 일간·주간 인사이트 (주간 테마 Top + 산업 흐름, 일간 핵심 3줄) (완료)
4. 대시보드 (목록·필터·요약 보기·원문) — `web/`, Vercel 배포

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
두 개의 GitHub Actions 워크플로가 이어서 돈다.

1. `daily-pipeline` (평일 KST 09/12/18시): 수집(collect) + PDF 텍스트
   추출(extract). 하나증권 전체 리서치 피드에서 신규 리포트만 저장하고 커밋한다.
2. `process-reports` (1번이 성공하면 자동 실행, 수동 실행도 가능):
   `scripts/process_reports.py`가 아직 `summary`가 없는 리포트를 골라
  요약·리포트별 인사이트·태깅 → 테마 병합 → 영향받은 주의 산업 브리핑(주 2건 이상 산업만)과
   주간 인사이트 → 해당 발행일 다이제스트까지 다시 만들고 커밋한다. 각 단계 규칙은
   `skills/*/SKILL.md`를 프롬프트에 그대로 넣어 따르게 한다.

LLM은 Claude Code CLI(`claude -p`, 도구 비활성화)를 로그인 토큰으로 호출한다.
파일 입출력은 파이썬 스크립트가 결정적으로 처리하고, LLM에는 텍스트만 주고받는다.

### 가공 단계 설정
1. 로컬에서 `claude setup-token` 실행 → 출력된 토큰을 저장소
   Settings → Secrets and variables → Actions → Secret
   `CLAUDE_CODE_OAUTH_TOKEN`으로 등록.
2. (선택) 모델을 고정하려면 Variable `CLAUDE_MODEL`을 등록 (비우면 계정 기본값).
3. 밀린 리포트는 실행당 최대 30건(`limit`)씩 처리된다. 한 번에 더 처리하려면
   Actions에서 `process-reports`를 수동 실행하며 `limit`을 키운다.
   브리핑/다이제스트만 다시 만들려면 `limit=0`, `redo_date=YYYY-MM-DD`.
4. 분류 체계(`config/taxonomy.json`)를 바꿨으면 `retag`를 체크해 수동 실행한다.
   요약만 입력으로 전체를 10건씩 다시 태깅하고 모든 브리핑/다이제스트를 재생성한다.
5. 프롬프트나 인사이트 형식(`skills/*`)만 바꿨으면 `redo_all`로 재태깅 없이 전체를 다시 만든다.

### 기존 리포트 인사이트 백필

기존 요약과 분류를 보존한 채 누락된 개별 리포트 인사이트만 생성하려면 전용
모드를 명시적으로 실행한다. 먼저 5건만 생성해 품질을 검수한다.

GitHub의 **Actions → process-reports → Run workflow**에서 `limit`을 `5`로
입력하고 `backfill_insights`를 체크해 실행한다. 등록된
`CLAUDE_CODE_OAUTH_TOKEN` Secret을 사용하며, 실행 결과는 워크플로가 자동으로
커밋한다. `backfill_insights`를 체크하지 않으면 평소 요약 파이프라인으로 실행된다.

동일한 작업을 인증된 로컬 환경에서 실행할 때는 다음 명령을 사용한다.

```bash
git diff -- data/reports data/industries data/themes insights digest
python scripts/process_reports.py --limit 5 --backfill-insights
git diff -- data/reports data/industries data/themes insights digest
```

두 번째 diff에서 대상 리포트의 `insight`, `insight_generated_at` 외 필드가
바뀌지 않았고 인사이트 품질이 적절한지 확인한다. 검토를 통과한 뒤 남은 전체
대상보다 큰 limit으로 확대한다(0은 처리하지 않으므로 충분히 큰 양수를 쓴다).

```bash
python scripts/process_reports.py --limit 10000 --backfill-insights
```

백필 모드는 `daily_series`, 요약이 없거나 PDF 추출 오류가 있는 레코드를 제외하며,
산업·테마 인덱스와 브리핑·주간 인사이트·다이제스트를 재생성하지 않는다.

### AI 논리 평가 (evaluate-reports)

개별 리포트마다 "근거에서 결론까지의 논리가 얼마나 튼튼한가"를 평가해 리포트 JSON의
`claim_review`에 붙이고, 대시보드 리포트 상세에 **AI 논리 평가** 카드로 보여준다.
결론의 정답 여부나 투자 의견이 아니라 논리 사슬(약한 고리 / 설득력 있는 부분 /
더 설득력 있으려면)을 평가한다. 평가 기준은 `skills/evaluate-report-claims/SKILL.md`이며,
이 파일 전체가 시스템 프롬프트로 들어간다.

- **모델**: 이 단계에서만 Opus를 쓴다. 기본 `claude-opus-5-5`, 바꾸려면 저장소 Variable
  `CLAUDE_REVIEW_MODEL`. 요약·태깅 등 나머지 단계는 기존 `CLAUDE_MODEL`을 그대로 쓴다.
- **실행 방식**: 자동으로 전체를 평가하지 않는다. 대시보드 버튼이나 수동 실행으로 지정한
  리포트만 평가한다. 인증은 같은 `CLAUDE_CODE_OAUTH_TOKEN`(구독 사용량 공유)을 쓴다.
- **수동 실행**: Actions → evaluate-reports → Run workflow. `report_ids`(쉼표 구분) 또는
  `date` 중 하나는 필수, `redo`(이미 있어도 다시 생성), `limit`.
- **대시보드 버튼**: 리포트 상세의 "AI 평가 생성 / 다시 평가" 버튼이 같은 워크플로를
  그 리포트만 대상으로 실행한다. 평가(1~3분) → 커밋 → Vercel 재빌드 후 반영된다.
  Vercel 환경변수 `GITHUB_DISPATCH_TOKEN`이 필요하다 (아래 Vercel 연결 참고).

로컬 실행: `python scripts/evaluate_reports.py --ids hana_1288828 --redo` (로그인된 claude CLI 필요)

### 산출물
- `insights/weekly/{ISO주차}.md` — **주간 인사이트** (이번 주 한 줄 헤드라인 / 이번 주 한눈에 /
  테마 Top 3~5 / 산업 흐름 / 다음 주 체크포인트). 같은 이름의 `.json`에 테마·산업별 report_id 목록.
- `digest/{발행일}.md` — **일간 다이제스트**. 주식 용어에 익숙하지 않은 독자 기준의 쉬운 말로
  (오늘 한 줄 / 오늘의 핵심 3개 / 용어 풀이 / 데일리 코멘트 / 산업별 브리핑 업데이트).
  그날 개별 리포트 목록은 대시보드가 따로 보여주므로 다이제스트에 쓰지 않는다.
- `data/industries/{산업}/briefs/{ISO주차}.md` — 그 주 리포트 2건 이상인 산업의 브리핑
- `data/themes/aliases.json` — 병합된 테마 이름 → 대표 이름 (`consolidate-themes`)

### 분류 체계
- **desk**: 리포트 성격. breadcrumb 카테고리로 결정적으로 매핑 (산업·기업 /
  시황·전략 / 퀀트 / 포트폴리오 / 채권·금리 / 크레딧 / 디지털자산 / 데일리)
- **industries**: 리포트가 주제로 다루는 산업 0~2개, 고정 목록 안에서만
- **themes**: 산업을 가로지르는 이슈 1~3개 (예: "FOMC 금리 인상", "미중 정상회담")

규칙은 `skills/tag-industry/SKILL.md`, 목록은 `config/taxonomy.json`.

인증 실패(401)나 구독 사용량 한도(429)면 즉시, 그 외 오류는 연속 3회면 중단한다.
한 건이라도 실패하면 그때까지 결과만 커밋하고 잡을 실패로 표시하며, 남은
리포트는 다음 실행에서 이어서 처리된다. 사용량 한도는 구독 플랜 단위라 대량
재처리(retag 등)는 한도가 넉넉한 시간에 돌린다.

수집 결과: `data/reports/{발행일}/hana_{bbsSeq}.json`
```
report_id, report_type(individual|daily_series), title, analyst,
published_date, published_time, category, breadcrumb, preview_text,
pdf_url, pdf_filename, source_url, collected_at, pdf_text, (pdf_error)
# process-reports가 덧붙이는 필드
summary, insight(individual만: 변화·의미·확인 포인트), summarized_at, insight_generated_at,
# evaluate-reports가 덧붙이는 필드 (individual만)
claim_review { strength(탄탄함|보통|약함), markdown, input(pdf|preview), model, generated_at }
desk,
industries(individual만), themes(individual만), tagged_at
```
PDF 추출에 실패한 리포트는 `pdf_error`와 함께 저장되고, seen 인덱스에
들어가지 않으므로 다음 실행에서 재시도된다.

## 대시보드 (web/)
Next.js 앱. 빌드할 때 저장소의 `data/`, `insights/`, `digest/`, `config/`를 읽어 모든
페이지를 정적으로 생성하고, 사이트 전체를 로그인 페이지(`/login`) 뒤에 둔다.
로그인하면 서명된 HttpOnly 쿠키로 30일간 유지되고, 비밀번호를 바꾸면 기존 세션은 모두 끊긴다.
`main`에 커밋이 올라올 때마다(수집·가공 워크플로 포함) Vercel이 다시 빌드하므로
별도 배포 작업은 없다.

페이지: 홈(이번 주 한눈에·최근 발행일 핵심·최근 리포트) / 주간 인사이트 / 일간
다이제스트 / 리포트 목록(데스크·산업·테마 필터, 검색) / 리포트 상세(요약·원문 링크·
추출 원문) / 테마별 / 산업별(주간 브리핑 포함)

시각화 확장 방향과 화면·집계·단계별 구현 기준은
[`docs/dashboard-visualization-plan.md`](docs/dashboard-visualization-plan.md)에 정리되어 있다.
유사 서비스에서 차용한 패턴과 제외한 패턴은
[`docs/dashboard-benchmark.md`](docs/dashboard-benchmark.md)에 정리되어 있다.
개발 시 적용할 데이터 계약, 화면 요구사항, 테스트와 완료 조건은
[`spec.md`](spec.md)를 기준으로 한다.
리포트별 인사이트의 다음 구현 단계와 코딩 에이전트용 작업 프롬프트는
[`docs/report-insight-next-step-prompt.md`](docs/report-insight-next-step-prompt.md)에 정리되어 있다.

### Vercel 연결
1. Vercel → Add New → Project → 이 저장소 Import
2. **Root Directory: `web`** (Framework Preset은 Next.js로 자동 인식)
3. Root Directory 설정 아래 **"Include files outside of the Root Directory in the
   Build Step"이 켜져 있는지 확인** (빌드가 `../data` 등을 읽는다)
4. Environment Variables
   - `DASHBOARD_PASSWORD` (필수): 접속 비밀번호. 없으면 사이트가 503을 낸다
   - `DASHBOARD_USER` (선택): 접속 아이디, 기본값 `me`
   - `DASHBOARD_SECRET` (선택): 세션 서명 키. 없으면 아이디·비밀번호에서 만든다
   - `GITHUB_DISPATCH_TOKEN` (선택): "AI 평가" 버튼용. GitHub → Settings → Developer settings
     → Fine-grained tokens에서 **이 저장소만, Repository permissions → Actions: Read and write**로
     발급한다. 없으면 버튼이 비활성화된다. 다른 저장소라면 `GITHUB_REPO`(기본 `YUJAEYUN/f_report`),
     기본 브랜치가 다르면 `GITHUB_REF`(기본 `main`)도 지정
5. Deploy → 접속하면 로그인 페이지로 이동한다

로컬 확인: `cd web && npm install && npm run build && DASHBOARD_PASSWORD=... npm start`
(개발 모드 `npm run dev`는 비밀번호 없이 열린다)

## 유의사항
- 대상 사이트의 robots.txt는 Googlebot/Yeti 외 자동화 접근을 Disallow 한다.
  요청 간 1.5초 딜레이를 두고 있으며, 정기 실행을 멈추려면 워크플로의
  `schedule:` 블록을 주석 처리한다.
- `pdf_text`에는 리포트 원문 텍스트가 들어간다. 저장소가 public이면
  원문이 공개 재배포되므로 저장소를 private으로 두는 것을 권장한다.
  대시보드도 원문을 보여주므로 `DASHBOARD_PASSWORD` 없이 공개 배포하지 않는다.

## 디렉터리 구조
```
skills/                 각 파이프라인 단계의 SKILL.md (언제/입력/처리절차/출력형식/주의사항)
scripts/
  collectors/base.py    공통 수집기 인터페이스
  collectors/hana.py    하나증권 어댑터 (전체 피드 list.cmd 파싱)
  pdf_extract.py        PDF 바이트 -> 텍스트 (메모리 전용)
  report_index.py       seen_reports.json 기반 중복 방지
  run_pipeline.py        collect -> extract 오케스트레이션
  process_reports.py     summarize -> tag -> brief -> digest 오케스트레이션
  evaluate_reports.py    개별 리포트 논리 평가 (claim_review, Opus)
  llm.py                 Claude Code CLI(headless) 호출 래퍼
data/
  index/seen_reports.json   수집 완료 report_id 마스터 인덱스
  reports/{date}/{id}.json  리포트별 메타데이터 + PDF 추출 텍스트 (date = 발행일)
  industries/{industry}/    산업별 이력 + 주간 브리핑
  themes/index.json         테마별 report_id 목록
  themes/aliases.json       병합된 테마 이름 -> 대표 이름
insights/weekly/{week}.md  주간 인사이트 (+ .json)
config/taxonomy.json       desk 매핑 + 산업 목록
digest/{date}.md         오늘의 다이제스트
```

## 로컬 실행
```
pip install -r requirements.txt
python scripts/run_pipeline.py --max-pages 3            # 최근 30건까지
python scripts/run_pipeline.py --max-pages 3 --skip-pdf # 메타데이터만
python scripts/process_reports.py --limit 5             # 로그인된 claude CLI 필요
```
첫 실행은 `--max-pages` 만큼 과거로 거슬러 올라가고, 이후 실행은 이미
본 리포트만 있는 페이지가 나오면 멈춘다.
