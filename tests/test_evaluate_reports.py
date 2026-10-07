import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import evaluate_reports as ev
from scripts.llm import LLMError, LLMRateLimitError

BODY = "**총평**: 근거가 결론을 대체로 뒷받침합니다.\n\n## 약한 고리\n" + "가" * 300 + "\n\n논리에 대한 평가이며 투자 의견이 아닙니다."


def report(rid, date="2026-10-01", **kw):
    r = {
        "report_id": rid, "report_type": "individual", "title": "t", "published_date": date,
        "summary": {"one_liner": "요약"}, "pdf_text": "본문",
    }
    r.update(kw)
    return r


class ParseReviewTest(unittest.TestCase):
    def test_extracts_strength_and_body(self):
        out = ev.parse_review("**논리 강도: [보통]**\n\n" + BODY)
        self.assertEqual(out["strength"], "보통")
        self.assertTrue(out["markdown"].startswith("**총평**"))

    def test_tolerates_fence_and_preamble(self):
        out = ev.parse_review("```markdown\n평가입니다.\n**논리 강도: 탄탄함** (요약 기준)\n" + BODY + "\n```")
        self.assertEqual(out["strength"], "탄탄함")

    def test_rejects_missing_strength(self):
        with self.assertRaisesRegex(LLMError, "논리 강도"):
            ev.parse_review(BODY)

    def test_rejects_short_body(self):
        with self.assertRaisesRegex(LLMError, "짧음"):
            ev.parse_review("**논리 강도: 약함**\n짧다")


class SelectTargetsTest(unittest.TestCase):
    def setUp(self):
        self.reports = [
            (Path("a"), report("hana_1")),
            (Path("b"), report("hana_2", claim_review={"strength": "보통"})),
            (Path("c"), report("hana_3", report_type="daily_series")),
            (Path("d"), report("hana_4", summary=None)),
            (Path("e"), report("hana_5", date="2026-10-02")),
        ]

    def ids(self, targets):
        return [r["report_id"] for _, r in targets]

    def test_default_skips_reviewed_and_ineligible_newest_first(self):
        self.assertEqual(self.ids(ev.select_targets(self.reports, [], [], False)), ["hana_5", "hana_1"])

    def test_redo_by_id_includes_reviewed(self):
        self.assertEqual(self.ids(ev.select_targets(self.reports, ["hana_2", "hana_3"], [], True)), ["hana_2"])

    def test_by_date(self):
        self.assertEqual(self.ids(ev.select_targets(self.reports, [], ["2026-10-02"], True)), ["hana_5"])


class InputKindTest(unittest.TestCase):
    def test_preview_only(self):
        kind, text = ev.input_kind({"pdf_text": None, "preview_text": "발췌"})
        self.assertIn("미리보기", kind)
        self.assertEqual(text, "발췌")

    def test_truncated_pdf(self):
        kind, text = ev.input_kind({"pdf_text": "가" * (ev.MAX_PDF_CHARS + 5)})
        self.assertIn("앞부분", kind)
        self.assertEqual(len(text), ev.MAX_PDF_CHARS)


class EvaluateTest(unittest.TestCase):
    def test_saves_review_and_stops_on_rate_limit(self):
        with tempfile.TemporaryDirectory() as d:
            paths = [Path(d) / f"{i}.json" for i in range(3)]
            targets = [(p, report(f"hana_{i}")) for i, p in enumerate(paths)]
            replies = ["**논리 강도: 약함**\n" + BODY, LLMRateLimitError("429")]
            with patch.object(ev, "ask", side_effect=replies) as ask:
                failed = ev.evaluate(targets, 10)
            self.assertTrue(failed)
            self.assertEqual(ask.call_count, 2)
            self.assertEqual(ask.call_args.kwargs["model"], ev.REVIEW_MODEL)
            self.assertIn("논리를 평가하는 분석가", ask.call_args.kwargs["system_prompt"])
            saved = targets[0][1]["claim_review"]
            self.assertEqual(saved["strength"], "약함")
            self.assertEqual(saved["input"], "pdf")
            self.assertTrue(paths[0].exists())
            self.assertFalse(paths[1].exists())


if __name__ == "__main__":
    unittest.main()
