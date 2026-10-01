# 리서치 트래커 대시보드 개발 명세

> 상태: 개발 착수 가능  
> 대상: `web/` Next.js 애플리케이션  
> 기준 문서: [`docs/dashboard-visualization-plan.md`](docs/dashboard-visualization-plan.md)  
> 벤치마크: [`docs/dashboard-benchmark.md`](docs/dashboard-benchmark.md)
> 범위: 대시보드 시각화 MVP(데이터 집계, 홈, 주간 변화표, 테마×산업 관계, 산업 추세)

## 1. 목적

사용자가 리서치 문서를 처음부터 모두 읽지 않고도 다음 질문에 답할 수 있게 한다.

1. 데이터가 최신이며 정상적으로 가공됐는가?
2. 이번 주에 새로 등장하거나 전주보다 확대된 테마는 무엇인가?
3. 그 테마는 어떤 산업과 함께 언급됐는가?
4. 그 판단을 구성한 리포트는 무엇인가?

제품은 투자 추천 도구가 아니다. 모든 수치는 **하나증권 개별 리포트의 언급량**이며 시장 중요도,
방향성, 수익률을 뜻하지 않는다.

## 2. 성공 기준

| ID | 사용자 과업 | 목표 |
|---|---|---:|
| S-1 | 최신 발행일과 가공 상태 확인 | 10초 이내 |
| S-2 | 이번 주 신규·확대 테마 1개 발견 | 30초 이내 |
| S-3 | 테마에서 연결 산업과 근거 리포트로 이동 | 3클릭 이내 |
| S-4 | 리포트 요약에서 증권사 원문으로 이동 | 2클릭 이내 |
| S-5 | 변화가 투자 신호가 아니라 언급량임을 설명 | 테스트 참여자 전원 |

정량 목표는 출시 보장이 아니라 구현 후 수동 사용성 테스트의 합격 기준이다.

## 3. 범위

### 3.1 MVP에 포함

- 빌드 시 전체 개별 리포트에서 주간 집계를 생성하는 순수 함수
- 데이터 최신성·품질 상태
- 선택 주와 직전 ISO 주의 테마 변화
- 테마×산업 공동 언급 행렬
- 최근 최대 8주의 산업별 언급량
- 홈의 상태 바, 변화 요약, 관계 뷰, 최신 다이제스트, 최근 리포트
- 주간 페이지의 테마 변화표와 근거 리포트 링크
- 테마·산업 허브의 최근 변화 중심 정렬
- 기간·테마·산업 필터를 나타내는 URL 검색 파라미터
- 그래픽과 동등한 HTML 표
- 모바일, 키보드, 다크 모드

### 3.2 MVP에서 제외

- 주가, 수익률, 거래량, 컨센서스 등 외부 시장 데이터
- 매수·매도 점수, 감성 점수, 테마 랭킹 추천
- `pdf_text`의 브라우저 전송 또는 전체 본문 검색
- 사용자 계정별 북마크·알림·포트폴리오
- 8주 미만 데이터에 대한 이동평균, 계절성, 이상치 판정
- 실시간 API, 데이터베이스, 별도 집계 서버
- `daily_series`를 포함한 테마·산업 빈도 계산

## 4. 용어와 집계 규칙

### 4.1 용어

- **선택 주**: 화면이 표시하는 ISO 주차. 기본값은 데이터에 존재하는 가장 최신 주다.
- **직전 주**: 선택 주의 달력상 바로 전 ISO 주차다. 데이터가 있는 이전 주로 대체하지 않는다.
- **언급량**: 조건에 맞는 고유 `report_id` 수다.
- **공동 언급**: 하나의 리포트에 특정 테마와 산업이 함께 태깅된 상태다. 인과관계를 뜻하지 않는다.
- **근거 다양성**: 고유 애널리스트 수와 고유 데스크 수다.

### 4.2 공통 규칙

1. `report_type === "individual"`만 집계한다.
2. 리포트 하나에 같은 태그가 중복돼도 한 번만 센다.
3. 날짜는 `YYYY-MM-DDT00:00:00Z`로 해석하고 UTC 기준 ISO 주차를 계산한다.
4. 테마는 `data/themes/aliases.json` 적용 후 대표 이름으로 집계한다.
5. 애널리스트가 `null` 또는 빈 문자열이면 고유 수에서 제외하고 `unknownAnalystCount`에 센다.
6. 산업이나 테마가 비어 있는 리포트는 품질 집계에는 포함하되 행렬에서 숨기지 않고 `미분류`로 센다.
7. 모든 배열의 리포트 ID는 중복 제거 후 최신 발행순으로 정렬한다.
8. 비율 변화는 계산하지 않는다. 표본이 작으므로 절대 건수와 절대 증감만 표시한다.

### 4.3 테마 상태

선택 주 건수를 `current`, 직전 주 건수를 `previous`라고 한다.

| 상태 | 조건 | UI 라벨 |
|---|---|---|
| `new` | `current > 0 && previous === 0` | 신규 |
| `up` | `current > previous && previous > 0` | 확대 |
| `steady` | `current === previous && current > 0` | 지속 |
| `down` | `current < previous && current > 0` | 약화 |
| `dropped` | `current === 0 && previous > 0` | 이번 주 미등장 |

기본 변화 목록에는 `new`, `up`, `steady`, `down`만 표시한다. `dropped`는 “이번 주 미등장 보기”를
켰을 때만 표시한다. 정렬은 상태 우선순위 `new → up → steady → down → dropped`, 증감 절댓값 내림차순,
`current` 내림차순, 한국어 이름 오름차순이다.

## 5. 데이터 계약

### 5.1 타입

다음 타입은 `web/lib/dashboard.ts`에 선언한다. 필드명과 의미를 임의로 바꾸지 않는다.

```ts
export type TrendStatus = "new" | "up" | "steady" | "down" | "dropped";

export type DashboardQuality = {
  totalReports: number;
  individualReports: number;
  unsummarized: number;
  pdfErrors: number;
  unclassifiedIndustries: number;
  unclassifiedThemes: number;
};

export type ThemeWeeklyStat = {
  name: string;
  count: number;
  reportIds: string[];
  analystCount: number;
  unknownAnalystCount: number;
  deskCount: number;
  industries: Record<string, number>;
};

export type IndustryWeeklyStat = {
  name: string;
  count: number;
  reportIds: string[];
  analystCount: number;
  unknownAnalystCount: number;
  briefExists: boolean;
};

export type DashboardWeek = {
  week: string;
  startDate: string;
  endDate: string;
  throughDate: string; // 해당 주에 실제 데이터가 존재하는 마지막 발행일
  reportCount: number;
  themes: ThemeWeeklyStat[];
  industries: IndustryWeeklyStat[];
};

export type ThemeChange = {
  name: string;
  current: number;
  previous: number;
  delta: number;
  status: TrendStatus;
  reportIds: string[];
  analystCount: number;
  deskCount: number;
  industries: Array<{ name: string; count: number }>;
};

export type ThemeIndustryCell = {
  theme: string;
  industry: string;
  count: number;
  reportIds: string[];
};

export type DashboardSnapshot = {
  generatedAt: string;
  latestPublishedDate: string | null;
  quality: DashboardQuality;
  weeks: DashboardWeek[];
};
```

### 5.2 공개 함수

```ts
buildDashboardSnapshot(reports: Report[], options?: { generatedAt?: string }): DashboardSnapshot
themeChanges(snapshot: DashboardSnapshot, week: string): ThemeChange[]
themeIndustryMatrix(snapshot: DashboardSnapshot, week: string): ThemeIndustryCell[]
industryTrend(snapshot: DashboardSnapshot, industry: string, limit?: number): Array<{ week: string; count: number }>
```

- 네 함수는 입력 객체를 변경하지 않는 순수 함수여야 한다.
- `generatedAt`을 테스트에서 주입할 수 있어야 한다.
- 알 수 없는 주차를 전달하면 예외 대신 빈 배열을 반환한다.
- `industryTrend`의 기본 `limit`은 8이며, 데이터가 적으면 존재하는 주만 반환한다.
- `buildDashboardSnapshot`은 주차 최신순, 각 주 내부 테마·산업은 건수 내림차순으로 반환한다.

### 5.3 데이터 로딩

- `web/lib/data.ts`가 파일 시스템 읽기를 계속 담당한다.
- 기존 `Report` 타입에 `summarized_at?: string`, `tagged_at?: string`을 추가한다.
- `dashboardSnapshot()`을 추가하고 프로세스 내에서 한 번만 계산해 캐시한다.
- snapshot에는 `pdf_text`, `preview_text`, 전체 `summary`를 넣지 않는다.
- `generatedAt`은 가장 최근 `summarized_at` 또는 주간 메타 `generated_at`을 우선 사용한다.
  둘 다 없으면 빌드 시각을 사용하고 UI에 `빌드 시각`이라고 표시한다.
- 별칭 파일이 없거나 비어 있어도 빌드를 실패시키지 않고 원래 테마명을 사용한다.

## 6. URL 계약

| 파라미터 | 값 | 기본값 | 잘못된 값 처리 |
|---|---|---|---|
| `week` | `YYYY-Www` | 최신 데이터 주차 | 최신 주차로 대체 |
| `period` | `1w`, `4w`, `8w` | `1w` | `1w`로 대체 |
| `theme` | 대표 테마명 | 없음 | 필터 해제 |
| `industry` | taxonomy 산업명 | 없음 | 필터 해제 |
| `sort` | `delta`, `count`, `recent` | 화면별 기본값 | 화면별 기본값 |
| `dropped` | `1` | 없음 | `1` 외에는 해제 |

- 사용자가 필터를 변경하면 `router.replace`로 URL을 갱신하되 다른 유효 파라미터는 보존한다.
- URL로 직접 접근하거나 새로고침해도 같은 상태가 복원돼야 한다.
- 한국어 값은 `URLSearchParams`에 맡겨 인코딩하고 수동 이중 인코딩하지 않는다.
- 차트 클릭, 표 행 클릭, 브라우저 뒤로 가기가 같은 필터 상태를 가리켜야 한다.

## 7. 화면 요구사항

### 7.1 공통

- 최대 콘텐츠 폭은 데스크톱에서 1200px로 늘리되 읽기 문단은 `70ch`를 넘기지 않는다.
- 모든 정량 컴포넌트에 집계 기간, `개별 리포트 언급량 기준`, 표본 수를 표시한다.
- 선택 주가 최신 주이면 `throughDate`를 이용해 `YYYY-MM-DD까지 집계`라고 표시한다. 주가 끝났다고
  추정하거나 완결된 주간 통계처럼 표현하지 않는다.
- 상태는 색만으로 표현하지 않고 아이콘, 라벨, 숫자를 함께 사용한다.
- 차트에는 항상 같은 데이터의 표 보기 전환 또는 바로 뒤따르는 대체 표가 있어야 한다.
- 툴팁에만 필수 정보를 넣지 않는다.
- 모든 근거 리포트는 기존 `/reports/[id]` 상세 페이지로 연결한다.

### 7.2 홈 `/`

위에서 아래로 다음 순서를 지켜야 한다.

1. **데이터 상태 바**
   - 최신 발행일, 마지막 가공 시각, 미요약 수, PDF 오류 수
   - `unsummarized > 0` 또는 `pdfErrors > 0`이면 경고 표시
2. **무엇이 달라졌나**
   - 선택 주의 `new`, `up`, `down` 중 정렬 상위 5개
   - 각 행에 상태, 테마명, `previous → current`, delta, 근거 수
   - 행 선택 시 `/themes/[name]?week=...`으로 이동
   - 긴 주간 설명보다 먼저 배치
3. **이번 주 한눈에**
   - 기존 주간 인사이트의 한눈에 섹션
   - 기본 표시 최대 2줄, 펼치기 버튼 제공
4. **테마×산업 관계**
   - 상위 테마 5개 × 상위 산업 8개
   - 셀 값은 고유 리포트 수
   - 셀 선택 시 `/reports?week=...&theme=...&industry=...`로 이동
5. **최근 발행일 핵심**
   - 실제 개별 리포트가 있는 최신 날짜를 사용
6. **최근 리포트**
   - 개별 리포트 최신 8건

이번 주 데이터가 없으면 상태 바와 최근 발행일·리포트는 유지하고 변화/관계 영역에 명시적인 빈 상태를 보인다.

### 7.3 주간 `/weekly/[week]`

- 기존 주간 마크다운 앞에 테마 변화표를 배치한다.
- 열: 상태, 테마, 이번 주, 전주, 증감, 고유 애널리스트, 고유 데스크, 연결 산업
- 기본 정렬은 4.3의 상태 정렬 규칙을 따른다.
- 테마 행을 펼치면 근거 리포트의 제목, 발행일, 애널리스트를 표시한다.
- 직전 주 데이터가 없으면 전주 숫자를 `—`로 표시하고 `비교할 직전 주 데이터 없음`을 노출한다.
- 주간 본문의 리포트 ID는 가능한 경우 리포트 제목 링크로 렌더링한다.

### 7.4 테마 허브 `/themes`

- 기존 누적 칩 목록을 비교 테이블로 교체한다.
- 열: 테마, 이번 주, 최근 4주, 전주 대비, 최근 등장일, 고유 애널리스트, 연결 산업
- 기본 정렬은 `delta`, 사용자가 `count`, `recent`로 변경할 수 있다.
- 모바일에서는 테마, 전주 대비, 이번 주만 1차 행에 보이고 나머지는 펼친다.
- 테마 상세에는 최초 등장일, 최근 등장일, 활성 주 수를 표시한다.
- 테마 상세 타임라인은 주차별 `핵심 주장 → 근거 리포트 → 리스크` 순서를 사용한다.

### 7.5 산업 허브 `/industries`

- taxonomy의 모든 산업을 0건 포함해 표시한다.
- 열: 산업, 이번 주, 최근 4주, 전주 대비, 최근 브리핑, 상위 연결 테마
- 산업명 선택 시 기존 `/industries/[name]`으로 이동한다.
- 언급량 0과 브리핑 없음은 서로 다른 상태로 표시한다.

### 7.6 리포트 탐색 `/reports`

- 기존 검색과 데스크·산업·테마 필터를 유지한다.
- `week`, `theme`, `industry` URL 파라미터를 초기 필터로 읽는다.
- 활성 필터 칩과 전체 초기화 버튼을 제공한다.
- 결과가 0건이면 어떤 필터가 적용됐는지와 초기화 동작을 표시한다.

## 8. 컴포넌트와 파일 구조

```text
web/
  app/
    page.tsx                         홈 조립(서버)
    weekly/[week]/page.tsx           주간 조립(서버)
    themes/page.tsx                  테마 허브
    industries/page.tsx              산업 허브
    globals.css                      토큰과 반응형 스타일
  components/dashboard/
    DataStatus.tsx                   상태 바(서버 가능)
    CollapsibleSummary.tsx           2줄 요약+펼침(클라이언트)
    ThemeChangeTable.tsx             정렬·펼침 표(클라이언트)
    ThemeIndustryHeatmap.tsx         ECharts 래퍼(클라이언트)
    ThemeIndustryFallback.tsx        동등한 HTML 표
    IndustrySparklines.tsx           산업 추세(클라이언트)
    DashboardEmpty.tsx               공통 빈 상태
  lib/
    dashboard.ts                     타입·순수 집계 함수
    dashboard.test.ts                집계 테스트
    data.ts                          파일 로딩·snapshot 캐시
```

- 서버 컴포넌트가 데이터를 집계하고 직렬화 가능한 최소 props만 클라이언트 컴포넌트에 전달한다.
- 차트 컴포넌트 외부에서 ECharts 타입이나 옵션을 사용하지 않는다.
- 범용 컴포넌트를 성급히 만들지 않는다. 두 화면 이상에서 실제 재사용할 때만 공통화한다.

## 9. 의존성 결정

### 9.1 도입

- `echarts`: heatmap, bar/line 시각화. `echarts/core`에서 필요한 모듈만 등록한다.
- `@tanstack/react-table`: 테마 변화표와 허브 표의 정렬·확장 상태.
- `lucide-react`: 상태·경고·이동 아이콘. 개별 아이콘만 import한다.
- 테스트 러너: 현재 프로젝트에 없으므로 구현 첫 커밋에서 `vitest`를 개발 의존성으로 추가한다.

### 9.2 사용 제약

- `echarts-for-react`는 추가하지 않는다. 내부 래퍼에서 `init`, `setOption`, `resize`, `dispose`를 관리한다.
- ECharts 기본 렌더러는 SVG다.
- `ThemeIndustryHeatmap`을 클라이언트 컴포넌트로 만들고 그 안에서 ECharts 모듈을 동적 import한다.
  차트 로드 전에도 제목과 대체 표에 접근할 수 있어야 한다.
- Tremor, shadcn/ui, Tailwind는 추가하지 않는다.
- 컴포넌트 테스트가 필요할 때 `@testing-library/react`, `@testing-library/user-event`, `jsdom`을
  개발 의존성으로 함께 추가한다.
- 새 의존성을 추가한 뒤 `npm run build` 결과의 route별 JS 크기를 변경 전과 비교해 PR에 기록한다.

### 9.3 차트 Spike 중단 조건

다음 중 하나라도 충족하면 MVP 히트맵은 ECharts 대신 CSS Grid 표로 출시한다.

- 프로덕션 정적 빌드 실패 또는 hydration 오류
- 360px에서 데이터 손실
- 키보드로 동등한 근거 목록에 도달 불가
- 차트와 대체 표의 셀 값 불일치
- 차트 코드가 사용하지 않는 주요 route에도 포함됨

## 10. 디자인 및 접근성

### 10.1 디자인 토큰

기존 CSS 변수에 다음 semantic token을 추가한다. 라이트·다크 모드를 모두 정의한다.

```css
--status-new;
--status-up;
--status-down;
--status-warning;
--chart-1;
--chart-2;
--chart-empty;
```

- `new`: 파랑 계열
- `up`: 초록 계열
- `down`: 중립 회색 계열
- `warning`: 주황 계열
- 빨강과 초록만으로 상태를 구분하지 않는다.

### 10.2 접근성

- 모든 버튼, 표 행 확장, 차트 대체 동작을 키보드로 실행할 수 있어야 한다.
- 포커스 링은 배경 대비 3:1 이상이며 제거하지 않는다.
- 아이콘은 장식이면 `aria-hidden`, 단독 의미면 접근 가능한 이름을 갖는다.
- 표는 `<table>`, `<thead>`, `<tbody>`, `<th scope>`를 사용한다.
- 정렬 버튼은 현재 방향을 `aria-sort`로 전달한다.
- 펼침 버튼은 `aria-expanded`와 대상 `aria-controls`를 제공한다.
- ECharts `aria` 옵션을 켜되 대체 표를 접근성의 기준 구현으로 삼는다.
- `prefers-reduced-motion: reduce`에서는 차트 초기 애니메이션을 끈다.

### 10.3 반응형

- 1280px: 비교표 전체 열과 히트맵을 나란히 표시할 수 있다.
- 768px: 한 열 레이아웃, 표는 필요한 경우 가로 스크롤한다.
- 360px: 히트맵 대신 대체 표를 기본 표시하고 핵심 열 외 정보는 행 펼침으로 제공한다.
- 수평 스크롤 영역은 키보드 포커스를 받을 수 있고 스크롤 가능함을 시각적으로 알려야 한다.

## 11. 오류 및 빈 상태

| 상황 | 동작 |
|---|---|
| 리포트 0건 | 페이지는 빌드되고 `아직 수집된 리포트가 없습니다` 표시 |
| 선택 주 없음 | 최신 주로 이동하거나 빈 상태 표시, 예외 금지 |
| 직전 주 없음 | 비교 불가 안내, 현재 값 유지 |
| 테마/산업 없음 | `미분류`로 집계하고 품질 수치 표시 |
| 별칭 파일 없음/오류 | 원래 이름 사용, 빌드 로그 경고 |
| 차트 로드 실패 | 대체 표 유지, 나머지 페이지 사용 가능 |
| 근거 report ID 없음 | 깨진 링크 대신 `원본 리포트 없음` 표시, 검증 테스트 실패 |

빈 상태는 영역을 숨기지 않는다. 사용자가 데이터 없음과 렌더링 실패를 구분할 수 있는 문구를 제공한다.

## 12. 테스트 명세

### 12.1 단위 테스트

`web/lib/dashboard.test.ts`에 최소 다음 케이스를 작성한다.

1. `daily_series` 제외
2. 동일 리포트 내 중복 태그 한 번만 집계
3. 일요일/월요일 및 ISO 연도 경계 주차
4. 달력상 직전 주가 비어 있을 때 이전 관측 주로 대체하지 않음
5. 별칭이 대표 이름으로 합쳐짐
6. 빈 산업·테마가 `미분류`로 집계됨
7. null 애널리스트가 고유 수에서 제외되고 unknown에 포함됨
8. `new/up/steady/down/dropped` 모든 상태
9. 상태·증감·건수·한국어 이름 정렬
10. 행렬 셀 count와 `reportIds.length` 일치
11. snapshot, 변화표, 행렬에서 원본 입력이 변경되지 않음
12. 존재하지 않는 주차가 빈 배열 반환

### 12.2 컴포넌트 테스트

- 변화표 정렬 및 행 펼침
- URL 파라미터에서 필터 초기화
- 필터 변경 시 다른 유효 파라미터 보존
- 빈 상태와 오류 상태 문구
- 차트 셀과 대체 표 셀이 같은 report ID 집합을 가짐
- 모든 변화 행과 0보다 큰 행렬 셀에서 근거 목록으로 이동 가능
- 키보드로 표 행 펼침 및 근거 링크 이동

### 12.3 통합 확인

- `npm test`
- `npm run build`
- 인증된 상태에서 홈, 주간, 테마, 산업, 리포트 route 응답 확인
- 360px, 768px, 1280px에서 시각 회귀 또는 스크린샷 확인
- 라이트·다크 모드 확인
- 키보드만으로 S-1~S-4 과업 수행

## 13. 성능 예산

- 홈 HTML 또는 RSC payload에 `pdf_text`가 포함되면 안 된다.
- 차트는 viewport에 들어오기 전까지 초기화하지 않아도 되며 대체 표는 즉시 보여야 한다.
- 최근 8주를 기본 데이터 범위로 하고 전체 근거 목록은 펼칠 때 렌더링한다.
- 홈의 Largest Contentful Paint 대상은 텍스트여야 하며 차트 로딩에 막히면 안 된다.
- 프로덕션 빌드에서 ECharts가 차트 미사용 route의 클라이언트 chunk에 포함되면 안 된다.
- 인증 가능한 실행 환경에서 Lighthouse 성능·접근성 각각 90 이상을 목표로 한다.

## 14. 구현 순서

각 단계는 독립 커밋과 검증 결과를 남긴다.

1. **집계 기반**
   - `dashboard.ts`, 타입, fixture, 단위 테스트
   - 완료: 집계 테스트 전부 통과
2. **차트 없는 정보 구조**
   - 상태 바, 변화표, URL 필터, 홈 재배치
   - 완료: S-1/S-2를 표만으로 수행 가능
3. **관계·추세 시각화 Spike**
   - ECharts 내부 래퍼, heatmap, 대체 표, 번들 비교
   - 완료: 9.3 중단 조건에 해당하지 않음
4. **허브와 드릴다운**
   - 테마·산업 비교표, `/reports` 교차 필터, 근거 링크
   - 완료: S-3/S-4 수행 가능
5. **접근성·반응형·회귀**
   - 세 viewport, 다크 모드, 키보드, 빈 상태, 빌드
   - 완료: 15절 Definition of Done 충족

## 15. Definition of Done

다음 항목을 모두 만족해야 MVP를 완료로 본다.

- [ ] 4절의 모든 집계 규칙이 단위 테스트로 고정됨
- [ ] 카드·표·차트·근거 목록의 수치가 동일함
- [ ] 홈에서 최신 상태와 상위 변화 5개를 확인 가능
- [ ] 주간 페이지에서 전주 비교와 근거 리포트 확인 가능
- [ ] 히트맵 또는 fallback 표에서 교차 필터된 리포트로 이동 가능
- [ ] URL 새로고침과 뒤로 가기 후 필터 상태 유지
- [ ] 360/768/1280px 및 라이트·다크 모드 확인
- [ ] 마우스 없이 핵심 과업 수행 가능
- [ ] `daily_series`가 집계에 포함되지 않음
- [ ] `pdf_text`가 대시보드 payload에 포함되지 않음
- [ ] `npm test`와 `npm run build` 통과
- [ ] 런타임 변경을 시각적으로 확인한 스크린샷 첨부
- [ ] 언급량이 투자 신호가 아니라는 안내가 정량 화면에 표시됨
- [ ] 테마 상세에서 최초·최근 등장일, 활성 주 및 주차별 근거 흐름 확인 가능

## 16. 개발 중 변경 관리

- 집계 정의, URL 계약, 데이터 타입을 바꾸려면 먼저 이 문서를 수정한다.
- 화면 배치나 문구처럼 데이터 의미를 바꾸지 않는 변경은 구현 PR에 사유를 기록한다.
- 외부 데이터, 알림, 북마크는 별도 spec 없이 MVP에 추가하지 않는다.
- 명세와 구현이 충돌하면 암묵적으로 구현을 따르지 않고, 명세 수정 또는 구현 수정 중 하나를 명시적으로 선택한다.
