# 리서치 맵

> 증권사 리서치 리포트를 모아, 한 단계 위에서 시장의 흐름을 보는 개인용 지도

![리서치 맵 홈 화면](docs/images/home.png)

## 배경

그룹포탈에 올라오는 글의 대부분은 리서치 자료다. 문제는 양이었다. 매일 쏟아지는 리포트를
다 읽기엔 부담스러웠고, 읽고 나서도 결국 무엇을 말하려는 건지 정리가 잘 되지 않았다.
핵심을 알아차리는 데만 오래 걸렸다.

그렇다고 가장 높은 추상화 단계만 보면 결론은 "매수", "매도" 같은 의견 한 줄로 끝난다.
궁금했던 건 그 의견에 이르는 **논리**였다. 왜 그렇게 보는지, 무엇이 달라져서 그런 결론이
나왔는지. 원문 전체와 의견 한 줄 사이, 그 중간 지점을 조율해 주는 소프트웨어를 만들어 보자는
생각에서 이 프로젝트가 시작됐다.

애널리스트들이 공개한 정보가 이미 주가에 반영되어 있다는 것도 안다. 그럼에도 이런 큰
배경을 아느냐 모르느냐의 차이는 시간이 지나며 쌓이고, 쌓이면 커질 것이라는 가설에서 출발했다.

## 접근: 위에서 아래로 (탑다운)

개인이 인터넷에 올라온 자료를 아무리 조합해도, 바닥의 데이터부터 쌓아 올라가는
바텀업 방식에는 구조적인 한계가 있다. 데이터 접근, 업계 맥락, 시간 모두 부족하다.

반면 국내 증권사가 발행하는 리서치 보고서에는 애널리스트 각자의 노하우와 인사이트,
데이터 분석 역량이 이미 담겨 있다. 이 저장소는 그 보고서들을 **재료**로 삼는다.
여러 리포트를 종합하고 가공해서 한 단계 위의 산출물을 만들고, 시장을 좀 더 멀리서 바라본다.

```
리포트 원문 ──▶ 요약·분류 ──▶ 테마·산업 단위로 묶기 ──▶ 주간·일간 흐름 ──▶ 대시보드
(애널리스트의 분석)  (리포트 1건)      (여러 리포트)            (시장 전체)
```

## 목적

- **거시적으로 보기**: 경제 시황과 사이클 산업의 흐름, 애널리스트들이 지금 주로 무엇을 보고
  있는지를 한눈에 본다. 어떤 테마가 떠오르고 사그라드는지, 업종을 보는 시각이 어떻게 바뀌는지.
- **비판적으로 읽기**: 리서치 보고서를 그대로 받아들이지 않도록 **AI 논리 평가**를 붙였다.
  결론이 맞을지가 아니라, 근거에서 결론까지 이어지는 논리가 어디서 강하고 어디서 약한지를 본다.
- **하지 않는 것**: 매수·매도 추천이나 목표주가 예측은 하지 않는다. 투자 판단의 근거가
  아니라 흐름을 이해하고 공부하기 위한 도구다.

## 이렇게 쓴다

| 언제 | 어디서 | 무엇을 |
|---|---|---|
| 매일 아침 1분 | 일간 다이제스트 | 오늘 리서치의 한 줄과 핵심 3개를 쉬운 말로 |
| 주말 10분 | 홈 · 주간 인사이트 | 테마 지도와 이번 주 한 줄, 테마별로 증권사가 어떻게 보는지 |
| 관심이 생기면 | 테마 · 산업 | 그 이슈가 몇 주에 걸쳐 어떻게 커지고 줄었는지, 어느 산업에서 나왔는지 |
| 깊이 볼 때 | 리포트 상세 | 핵심 포인트 → 변화·의미·확인 → AI 논리 평가 → 원문 |

![리포트 상세 화면](docs/images/report.png)

## 한계와 앞으로

- **아직 하나증권 한 곳뿐이다.** 지금 화면의 흐름은 한 증권사의 시각이다. 국내외 증권사를
  모두 넣을 예정이고, 그래야 "증권사들이 같은 말을 하는지, 다른 말을 하는지"를 볼 수 있다.
- **데이터베이스 없이 파일로 돌아간다.** 수집 결과와 가공 결과는 모두 저장소의 파일(JSON,
  Markdown)이고, 연산은 GitHub Actions 안에서 돈다. 증권사가 늘어 규모가 커졌을 때의
  아키텍처와 서버 구성은 추후에 고려한다.
- **증권사 리포트의 한계를 그대로 물려받는다.** 매수 의견 쪽으로 쏠리는 경향, 이미 주가에
  반영된 정보라는 점은 재료 자체의 한계다. AI 논리 평가와 여러 증권사 비교로 보완하려 한다.

## 로드맵

- [x] 수집·원문 추출 (하나증권)
- [x] 리포트 요약, 분류(desk·산업·테마), 리포트별 인사이트(변화 → 의미 → 확인)
- [x] 주간 인사이트·산업 브리핑·일간 다이제스트 (쉬운 말 버전)
- [x] 대시보드 (테마 지도, 주별 흐름, 리포트 상세)
- [x] AI 논리 평가 (대시보드 버튼으로 실행)
- [ ] 국내외 증권사 추가, 증권사 간 의견 비교 (같은 종목·같은 테마)
- [ ] 투자의견·목표주가 변화 추적
- [ ] 처리량이 늘었을 때의 비용·아키텍처 정리 (병렬 처리, 모델 분리, 저장 구조)

---

## 동작 방식

상시 서버 없이 GitHub Actions가 배치로 돌고, 모든 상태는 git 커밋으로 남는다.
`main`에 커밋이 올라오면 Vercel이 대시보드를 다시 빌드한다.

```
daily-pipeline (평일 KST 09·12·18시)
  수집: 하나증권 전체 리서치 피드에서 새 리포트만 → PDF 텍스트 추출(메모리에서만) → 커밋
        │ 성공하면
        ▼
process-reports
  요약·리포트별 인사이트·산업/테마 태깅 → 테마 이름 병합
  → 산업 브리핑(그 주 2건 이상 산업) → 주간 인사이트 → 일간 다이제스트 → 커밋
        │
        ▼
Vercel 재빌드 → 대시보드 (로그인 뒤)
        │ 리포트 상세의 "AI 평가" 버튼
        ▼
evaluate-reports (그 리포트만) → Opus로 논리 평가 → 커밋 → 재빌드
```

- 각 단계의 규칙은 `skills/*/SKILL.md`에 있고, 이 파일을 프롬프트에 그대로 넣어 따르게 한다.
- LLM은 Claude Code CLI(`claude -p`, 도구 비활성화)를 로그인 토큰으로 호출한다.
  어떤 파일을 읽고 어디에 쓸지는 파이썬 스크립트가 결정하고, LLM과는 텍스트만 주고받는다.

### 설계 원칙
- **PDF 원문은 커밋하지 않는다.** 내려받아 텍스트만 추출하고 바로 버린다.
- **개별 리포트와 데일리 종합물을 구분한다.** `daily_series`(Hana Guru Eye 등)는 그날의
  개별 이슈를 이미 요약한 것이라, 개별 리포트와 섞어 집계하면 같은 이슈가 두 번 세어진다.
- **수집기는 증권사별 어댑터로 분리한다.** `scripts/collectors/base.py`의 `ReportCollector`
  인터페이스를 구현하면 새 증권사를 붙일 수 있다. 지금 구현된 것은 `hana.py` 하나다.

## 대시보드 화면

| 화면 | 내용 |
|---|---|
| 홈 | 이번 주 테마 지도(면적=언급 건수, 색=지난주 같은 기간 대비), 이번 주 한 줄, 요일별 발행, 상위 테마 4주 추이, 산업 관심도 변화, 테마×산업, 최근 리포트 |
| 주간 | 주차별 헤드라인 목록 / 주간 상세: 테마 지도, 테마별 이야기와 추이, 산업 흐름, 다음 주 볼 것 |
| 테마 | 떠오르는·줄어든 테마, 주별 테마 흐름 표 / 테마 상세: 주별 언급, 출처 산업, 함께 나온 테마 |
| 산업 | 이번 주 관심도, 주별 산업 흐름 표 / 산업 상세: 주별 리포트, 다룬 테마, 종목별 최근 의견, 주간 브리핑 |
| 리포트 | 검색·필터 목록 / 리포트 상세: 핵심 포인트, 변화→의미→확인, AI 논리 평가, 정보 상자, 원문 |
| 일간 | 날짜별 헤드라인 목록 / 일간 상세: 오늘 한 줄, 핵심 3개, 용어 풀이, 데일리 코멘트, 산업 브리핑 |

색 규칙: 증감은 한국 시장 관례대로 **상승 빨강, 하락 파랑**. 논리 강도는 시장 색과 겹치지 않게
탄탄함 초록, 보통 중립, 약함 주황.

## 설정

### GitHub (Settings → Secrets and variables → Actions)
| 종류 | 이름 | 설명 |
|---|---|---|
| Secret | `CLAUDE_CODE_OAUTH_TOKEN` | 필수. 로컬에서 `claude setup-token` 실행 결과 (`sk-ant-oat01-…`) |
| Variable | `CLAUDE_MODEL` | 선택. 요약·태깅·브리핑 모델. 비우면 계정 기본값 |
| Variable | `CLAUDE_REVIEW_MODEL` | 선택. AI 논리 평가 모델. 비우면 `claude-opus-5-5` |

### Vercel
1. Add New → Project → 이 저장소 Import
2. **Root Directory: `web`**, 그 아래 **"Include files outside of the Root Directory in the
   Build Step"** 켜기 (빌드가 `../data` 등을 읽는다)
3. Environment Variables

| 이름 | 설명 |
|---|---|
| `DASHBOARD_PASSWORD` | 필수. 접속 비밀번호. 없으면 사이트가 503을 낸다 |
| `DASHBOARD_USER` | 선택. 접속 아이디, 기본 `me` |
| `DASHBOARD_SECRET` | 선택. 세션 서명 키. 없으면 아이디·비밀번호에서 만든다 (비밀번호를 바꾸면 세션이 모두 끊김) |
| `GITHUB_DISPATCH_TOKEN` | 선택. "AI 평가" 버튼용 Fine-grained PAT. **이 저장소만, Actions: Read and write**. 없으면 버튼이 비활성화된다 |
| `GITHUB_REPO`, `GITHUB_REF` | 선택. 기본 `YUJAEYUN/f_report`, `main` |

환경변수를 바꾼 뒤에는 Deployments에서 Redeploy해야 반영된다.

## 운영

### process-reports 수동 실행 (Actions → process-reports → Run workflow)
| 입력 | 쓰는 때 |
|---|---|
| `limit` | 한 번에 처리할 리포트 수 (기본 30). 밀린 리포트가 많을 때 키운다 |
| `redo_date` | 그 발행일의 브리핑·주간 인사이트·다이제스트만 다시 만들 때 (`limit=0`과 함께) |
| `retag` | 분류 체계(`config/taxonomy.json`)를 바꿨을 때. 전체 재태깅 + 전체 재생성 |
| `redo_all` | 프롬프트(`skills/*`)만 바꿨을 때. 재태깅 없이 테마 병합 + 전체 재생성 |
| `backfill_insights` | 기존 요약·분류는 두고 빠진 리포트별 인사이트만 채울 때. 먼저 `limit=5`로 품질 확인 |

인증 실패(401)나 사용량 한도(429)면 바로, 그 외 오류는 연속 3회면 멈춘다. 그때까지의 결과는
커밋하고 잡은 실패로 표시하며, 남은 리포트는 다음 실행에서 이어서 처리한다.

### AI 논리 평가 (evaluate-reports)
- 리포트 상세의 **AI 평가 생성 / 다시 평가** 버튼이 그 리포트만 대상으로 워크플로를 실행한다.
  평가(1~3분) → 커밋 → Vercel 재빌드 후 반영된다.
- 자동으로 전체를 평가하지 않는다. Actions에서 직접 실행할 때도 `report_ids`나 `date`가 필요하다.
- 평가 기준은 `skills/evaluate-report-claims/SKILL.md`이고, 파일 전체가 시스템 프롬프트로 들어간다.
- 로컬: `python scripts/evaluate_reports.py --ids hana_1288828 --redo` (로그인된 claude CLI 필요)

## 데이터

### 산출물
| 경로 | 내용 |
|---|---|
| `data/reports/{발행일}/hana_{번호}.json` | 리포트 1건 (메타데이터, 원문 텍스트, 요약, 인사이트, 분류, AI 평가) |
| `insights/weekly/{ISO주차}.md` (+`.json`) | 주간 인사이트: 이번 주 한 줄 / 한눈에 / 테마 Top 3~5 / 산업 흐름 / 다음 주 체크포인트 |
| `digest/{발행일}.md` | 일간 다이제스트 (쉬운 말): 오늘 한 줄 / 핵심 3개 / 용어 풀이 / 데일리 코멘트 / 산업별 브리핑 |
| `data/industries/{산업}/briefs/{ISO주차}.md` | 그 주 리포트 2건 이상인 산업의 브리핑 |
| `data/themes/index.json`, `aliases.json` | 테마별 report_id, 병합된 테마 이름 → 대표 이름 |

### 리포트 JSON 필드
```
# 수집 (daily-pipeline)
report_id, report_type(individual|daily_series), title, analyst, published_date, published_time,
category, breadcrumb, preview_text, pdf_url, pdf_filename, source_url, collected_at, pdf_text, (pdf_error)
# 가공 (process-reports)
summary, insight(individual만: 변화·의미·확인), summarized_at, insight_generated_at,
desk, industries(individual만), themes(individual만), tagged_at
# 평가 (evaluate-reports, individual만)
claim_review { strength(탄탄함|보통|약함), markdown, input(pdf|preview), model, generated_at }
```
PDF 추출에 실패한 리포트는 `pdf_error`와 함께 저장되고, 다음 실행에서 다시 시도한다.

### 분류 체계 (`config/taxonomy.json`, 규칙은 `skills/tag-industry/SKILL.md`)
- **desk**: 리포트 성격. 게시판 카테고리로 정해진다 (산업·기업 / 시황·전략 / 퀀트 / 포트폴리오 /
  채권·금리 / 크레딧 / 디지털자산 / 데일리)
- **industries**: 리포트가 주제로 다루는 산업 0~2개, 고정 목록 안에서만
- **themes**: 산업을 가로지르는 이슈 1~3개 (예: "3분기 어닝시즌", "AI 데이터센터 전력").
  같은 이슈가 다른 이름으로 갈라지면 테마 병합 단계가 대표 이름으로 합친다

## 비용과 한도

- **GitHub Actions**: private 저장소는 월 2,000분 무료. 지금(하나증권 한 곳)은 월 350분 안팎이고,
  대부분 AI 응답을 기다리는 시간이다.
- **Claude**: 구독 토큰을 쓰므로 토큰당 과금은 없고, 대신 구독 사용 한도를 개인 사용과 함께 쓴다.
- **증권사를 늘릴 때의 선택지**: AI 호출 동시 처리, 새 리포트가 없을 때 가공 건너뛰기,
  1차 가공만 가벼운 모델로 분리, 내 컴퓨터를 실행 서버(self-hosted runner)로 등록,
  API 키와 Batch API로 전환.

## 유의사항

- 대상 사이트의 robots.txt는 Googlebot·Yeti 외 자동 접근을 막고 있다. 요청 사이에 1.5초
  간격을 두며, 정기 실행을 멈추려면 `daily-pipeline.yml`의 `schedule:` 블록을 주석 처리한다.
- `pdf_text`에 리포트 원문이 들어간다. **저장소는 private으로 두고**, 대시보드도
  `DASHBOARD_PASSWORD` 없이 공개 배포하지 않는다.

## 디렉터리 구조
```
skills/                     파이프라인 단계별 규칙 (SKILL.md)
scripts/
  collectors/base.py        수집기 공통 인터페이스
  collectors/hana.py        하나증권 어댑터
  pdf_extract.py            PDF → 텍스트 (메모리 전용)
  report_index.py           수집 완료 인덱스로 중복 방지
  run_pipeline.py           수집 → 추출
  process_reports.py        요약 → 태깅 → 테마 병합 → 브리핑 → 주간 인사이트 → 다이제스트
  evaluate_reports.py       AI 논리 평가
  llm.py                    Claude Code CLI 호출 래퍼
data/                       리포트, 산업 브리핑, 테마 인덱스
insights/weekly/            주간 인사이트
digest/                     일간 다이제스트
config/taxonomy.json        desk 매핑 + 산업 목록
web/                        대시보드 (Next.js, Vercel)
.github/workflows/          daily-pipeline, process-reports, evaluate-reports
```

## 로컬 실행
```bash
pip install -r requirements.txt
python scripts/run_pipeline.py --max-pages 3              # 최근 30건까지 수집
python scripts/run_pipeline.py --max-pages 3 --skip-pdf   # 메타데이터만
python scripts/process_reports.py --limit 5               # 가공 (로그인된 claude CLI 필요)
python -m unittest discover -s tests                      # 테스트

cd web && npm install && npm run dev                      # 대시보드 (개발 모드는 비밀번호 없이 열림)
```
첫 수집은 `--max-pages`만큼 과거로 거슬러 올라가고, 이후에는 이미 본 리포트만 있는 페이지가
나오면 멈춘다.

## 참고 문서
- [`spec.md`](spec.md): 데이터 계약, 화면 요구사항, 테스트·완료 조건
- [`docs/dashboard-visualization-plan.md`](docs/dashboard-visualization-plan.md): 시각화 확장 방향
- [`docs/dashboard-benchmark.md`](docs/dashboard-benchmark.md): 유사 서비스에서 차용·제외한 패턴
- [`docs/report-insight-next-step-prompt.md`](docs/report-insight-next-step-prompt.md): 리포트별 인사이트 작업 프롬프트
