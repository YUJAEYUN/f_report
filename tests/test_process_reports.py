import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.llm import LLMError
from scripts.process_reports import (
    backfill_insights,
    insight_backfill_targets,
    validate_insight,
    validate_summary,
)


class ValidateSummaryTest(unittest.TestCase):
    def test_individual_requires_and_normalizes_insight(self):
        report = {"report_type": "individual"}
        obj = {
            "summary": {"one_liner": "요약", "key_points": [1], "risk_factors": None},
            "insight": {
                "change": "  수요가 회복됐다. ",
                "implication": "가동률을 확인해야 한다.",
                "watch_points": [" 출하량 ", "", "마진", "재고"],
            },
        }

        summary, insight = validate_summary(report, obj)

        self.assertEqual(summary["key_points"], ["1"])
        self.assertEqual(summary["risk_factors"], [])
        self.assertEqual(insight["change"], "수요가 회복됐다.")
        self.assertEqual(insight["watch_points"], ["출하량", "마진", "재고"])

    def test_individual_rejects_missing_insight(self):
        report = {"report_type": "individual"}

        with self.assertRaisesRegex(LLMError, "insight 누락"):
            validate_summary(report, {"summary": {"one_liner": "요약"}})

    def test_daily_series_does_not_require_insight(self):
        summary, insight = validate_summary(
            {"report_type": "daily_series"},
            {"summary": {"items": [{"topic": "이슈", "note": "내용"}]}},
        )

        self.assertEqual(len(summary["items"]), 1)
        self.assertIsNone(insight)


class InsightBackfillTest(unittest.TestCase):
    def test_target_selection_excludes_ineligible_and_daily_series(self):
        reports = [
            (Path("eligible"), {"report_type": "individual", "summary": {"one_liner": "요약"}}),
            (Path("done"), {"report_type": "individual", "summary": {}, "insight": {}}),
            (Path("no-summary"), {"report_type": "individual"}),
            (Path("error"), {"report_type": "individual", "summary": {}, "pdf_error": "실패"}),
            (Path("daily"), {"report_type": "daily_series", "summary": {"items": []}}),
        ]

        self.assertEqual([path.name for path, _ in insight_backfill_targets(reports)], ["eligible"])

    def test_validate_insight_normalizes_response(self):
        insight = validate_insight({"insight": {
            "change": "  변화  ", "implication": " 의미 ",
            "watch_points": [" 지표1 ", "", "지표2", "지표3", "지표4"],
        }})

        self.assertEqual(insight, {
            "change": "변화", "implication": "의미", "watch_points": ["지표1", "지표2", "지표3"],
        })

    def test_validate_insight_rejects_invalid_responses(self):
        cases = [
            ({}, "insight 누락"),
            ({"insight": {"change": " ", "implication": "의미", "watch_points": ["지표"]}}, "change"),
            ({"insight": {"change": "변화", "implication": " ", "watch_points": ["지표"]}}, "implication"),
            ({"insight": {"change": "변화", "implication": "의미", "watch_points": "지표"}}, "형식 오류"),
            ({"insight": {"change": "변화", "implication": "의미", "watch_points": [" "]}}, "watch_points 누락"),
        ]
        for response, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(LLMError, message):
                validate_insight(response)

    def test_backfill_mock_preserves_existing_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            report = {
                "report_id": "r1", "report_type": "individual", "title": "제목",
                "published_date": "2026-09-01", "summary": {"one_liner": "기존 요약"},
                "desk": "산업·기업", "industries": ["반도체"], "themes": ["AI"],
                "tagged_at": "기존 시각", "preview_text": "본문",
            }
            path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
            immutable = copy.deepcopy({key: report[key] for key in
                                       ("summary", "desk", "industries", "themes", "tagged_at")})
            response = {"insight": {"change": "변화", "implication": "의미", "watch_points": ["지표"]}}

            with patch("scripts.process_reports.ask_json", return_value=response) as mocked:
                self.assertFalse(backfill_insights([(path, report)], 5))

            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual({key: saved[key] for key in immutable}, immutable)
            self.assertEqual(saved["insight"], response["insight"])
            self.assertIn("insight_generated_at", saved)
            mocked.assert_called_once()


if __name__ == "__main__":
    unittest.main()
