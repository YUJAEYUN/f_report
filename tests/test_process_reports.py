import unittest

from scripts.llm import LLMError
from scripts.process_reports import validate_summary


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


if __name__ == "__main__":
    unittest.main()
