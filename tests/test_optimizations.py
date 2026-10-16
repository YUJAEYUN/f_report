import datetime as dt
import gzip
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import process_reports as pr
from scripts import textstore
from scripts.textprep import focus_text

KST = dt.timezone(dt.timedelta(hours=9))


class TextStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"RAW_TEXT_DIR": self.tmp.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_roundtrip_and_layout(self):
        p = textstore.save_text("hk_1", "2026-10-14", "원문 텍스트")
        self.assertEqual(p, Path(self.tmp.name) / "text" / "2026-10" / "hk_1.txt.gz")
        r = {"report_id": "hk_1", "published_date": "2026-10-14"}
        self.assertEqual(textstore.load_text(r), "원문 텍스트")
        self.assertTrue(textstore.has_text(r))
        self.assertTrue(textstore.available())

    def test_same_text_same_bytes(self):
        a = textstore.save_text("x", "2026-10-14", "같은 내용").read_bytes()
        b = textstore.save_text("x", "2026-10-14", "같은 내용").read_bytes()
        self.assertEqual(a, b)  # mtime 고정: 다시 써도 git diff가 생기지 않는다
        self.assertEqual(gzip.decompress(a).decode(), "같은 내용")

    def test_legacy_inline_text_wins(self):
        self.assertEqual(textstore.load_text({"report_id": "y", "pdf_text": "예전"}), "예전")
        self.assertIsNone(textstore.load_text({"report_id": "missing", "published_date": "2026-10-14"}))


class FocusTextTest(unittest.TestCase):
    BODY = "본문 문단입니다. 목표주가 38만원으로 상향.\n" * 400  # 첫 장 범위(HEAD_KEEP)를 넘기도록

    def test_drops_axis_numbers_tables_and_compliance(self):
        head_table = "매출액 2,166.1 2,398.8 3,107.8 3,847.3\n"
        text = (head_table + "0\n20\n40\n25.9 25.12 26.3\n" + self.BODY +
                "영업이익 175.4 195.8 269.0 352.1 445.6 재고자산 257.0 270.8\n"
                "2024 2025 2026F 2027F 2028F\n" + "Compliance Notice\n고지문 " * 50)
        out, truncated = focus_text(text)
        self.assertIn("매출액 2,166.1", out)      # 첫 장 표는 남긴다
        self.assertNotIn("\n20\n", out)            # 차트 눈금
        self.assertNotIn("재고자산", out)           # 뒤쪽 재무제표 표
        self.assertNotIn("2026F 2027F", out)
        self.assertNotIn("고지문", out)
        self.assertFalse(truncated)

    def test_limits(self):
        out, truncated = focus_text("가나다 " * 10000)
        self.assertTrue(truncated)
        self.assertEqual(len(out), 16_000)
        out, _ = focus_text("가나다 " * 10000, "daily_series")
        self.assertEqual(len(out), 36_000)


class PublishScheduleTest(unittest.TestCase):
    def test_should_publish(self):
        noon = dt.datetime(2026, 10, 14, 12, 0, tzinfo=KST)
        evening = dt.datetime(2026, 10, 14, 18, 5, tzinfo=KST)
        self.assertFalse(pr.should_publish({"2026-10-14"}, noon))
        self.assertTrue(pr.should_publish({"2026-10-14"}, evening))
        self.assertTrue(pr.should_publish({"2026-10-13", "2026-10-14"}, noon))  # 어제 것이 밀려 있으면 바로

    def test_pending_roundtrip(self):
        with tempfile.TemporaryDirectory() as d, patch.object(pr, "PUBLISH_PENDING", Path(d) / "p.json"):
            self.assertEqual(pr.load_pending(), set())
            pr.save_pending({"2026-10-14", "2026-10-13"})
            self.assertEqual(pr.load_pending(), {"2026-10-13", "2026-10-14"})


if __name__ == "__main__":
    unittest.main()


class RecentWindowTest(unittest.TestCase):
    NOW = dt.datetime(2026, 10, 15, 18, 0, tzinfo=KST)

    def test_old_backfill_dates_are_skipped(self):
        keep, skipped = pr.split_recent({"2026-09-28", "2026-10-02", "2026-10-14", "2026-10-15"}, set(), self.NOW)
        self.assertEqual(keep, {"2026-10-14", "2026-10-15"})
        self.assertEqual(skipped, {"2026-09-28", "2026-10-02"})

    def test_explicit_redo_date_kept(self):
        keep, _ = pr.split_recent({"2026-09-28"}, {"2026-09-28"}, self.NOW)
        self.assertEqual(keep, {"2026-09-28"})


class SummarizeOrderTest(unittest.TestCase):
    def test_newest_first(self):
        def rep(rid, d):
            return (Path(f"/x/{rid}.json"), {"report_id": rid, "published_date": d, "report_type": "daily_series"})
        reports = [rep("old", "2026-09-28"), rep("new", "2026-10-15"), rep("mid", "2026-10-02")]
        seen = []

        def fake_ask(prompt):
            raise pr.LLMRateLimitError("stop")  # 첫 호출에서 멈추고 순서만 확인

        with patch.object(pr, "ask_json", side_effect=lambda p: seen.append(p) or fake_ask(p)), \
                patch.object(pr, "build_summary_prompt", side_effect=lambda r: r["report_id"]):
            pr.summarize_pending(reports, 3)
        self.assertEqual(seen, ["new"])


class RateLimitExitTest(unittest.TestCase):
    def test_rate_limit_sets_flag(self):
        with patch.object(pr, "RATE_LIMITED", False):
            pr.abort_reason(pr.LLMRateLimitError("429"))
            self.assertTrue(pr.RATE_LIMITED)
        with patch.object(pr, "RATE_LIMITED", False):
            pr.abort_reason(pr.LLMAuthError("401"))
            self.assertFalse(pr.RATE_LIMITED)


class PublishRateLimitTest(unittest.TestCase):
    def test_digest_stops_on_rate_limit(self):
        reports = [(Path(f"/x/{i}.json"), {"report_id": f"r{i}", "report_type": "individual", "published_date": d,
                                           "summary": {"one_liner": "x"}, "industries": [], "themes": []})
                   for i, d in enumerate(["2026-10-14", "2026-10-15"])]
        calls = []
        with patch.object(pr, "ask", side_effect=lambda p: calls.append(1) or (_ for _ in ()).throw(pr.LLMRateLimitError("429"))), \
                patch.object(pr, "RATE_LIMITED", False), patch.object(pr, "digest_events", return_value=[]):
            failed = pr.build_digests(reports, {"2026-10-14", "2026-10-15"})
            self.assertTrue(pr.RATE_LIMITED)
        self.assertEqual((failed, len(calls)), (1, 1))  # 첫 429에서 멈춘다
