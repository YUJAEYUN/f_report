# raw-text

리서치 맵의 리포트 원문 텍스트 저장 브랜치. main 브랜치와 히스토리를 공유하지 않는다.

- `text/{YYYY-MM}/{report_id}.txt.gz`: PDF에서 추출한 텍스트 (gzip, UTF-8). PDF 파일 자체는 저장하지 않는다.
- `daily-pipeline`이 새 리포트를 수집할 때 여기에 쓰고, `process-reports`·`evaluate-reports`가 읽기 전용으로 체크아웃한다.
- 대시보드(Vercel)는 main만 빌드하므로 이 원문은 화면으로 나가지 않는다.
- 읽고 쓰는 코드: main 브랜치의 `scripts/textstore.py`
