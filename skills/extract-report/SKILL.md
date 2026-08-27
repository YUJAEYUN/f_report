# extract-report

## 언제
collect-reports가 새 `RawReportItem`을 넘겨줄 때마다, PDF 본문을 텍스트로
확보해야 하는 시점에 실행한다. summarize-report보다 먼저다.

## 입력
- `RawReportItem` (pdf_url 포함)

## 처리절차
1. `pdf_url`을 GET으로 요청해 응답 바이트를 메모리(BytesIO)에서만 다룬다.
2. `scripts/pdf_extract.extract_text_from_pdf_bytes`로 페이지별 텍스트를
   추출해 하나의 문자열로 합친다.
3. 원본 PDF 바이트/파일은 이 함수가 반환하는 즉시 폐기한다 — 어떤 경로로도
   디스크에 `.pdf`로 쓰지 않는다.
4. 추출 실패(암호화된 PDF, 스캔 이미지라 텍스트가 없는 경우 등)는 예외를
   삼키지 말고 리포트 레코드에 `pdf_error`로 남기고, 해당 리포트의 나머지
   메타데이터(제목/애널리스트/발행일 등)는 정상 저장한다 — PDF 한 건의 실패가
   전체 배치를 죽이면 안 된다.

## 출력형식
`RawReportItem`에 `pdf_text: str` (또는 실패 시 `pdf_text: null` +
`pdf_error: str`)를 덧붙인 dict.

## 주의사항
- 요청 사이 최소 1.5초 딜레이 유지 (collect-reports와 동일한 예의).
- PDF가 매우 크면 텍스트도 커질 수 있으니, 이 단계의 출력을 그대로
  `data/reports/`에 커밋하지 않는다 — summarize-report를 거쳐 구조화된
  요약만 커밋 대상이 된다 (원문 전체 텍스트를 리포지토리에 영구 저장하지 않는다).
