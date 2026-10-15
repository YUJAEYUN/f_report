import tempfile
import unittest
from pathlib import Path

from scripts import drawdown as dd
from scripts.llm import LLMError

CFG = dd.CONFIG


def report(rid, date, kind="individual", desk="시황·전략", text="", themes=None, **kw):
    r = {
        "report_id": rid, "report_type": kind, "title": "t", "published_date": date,
        "desk": desk, "themes": themes or [], "broker": "테스트증권",
        "summary": {"one_liner": text} if kind == "individual" else {"items": [{"topic": "시황", "note": text}]},
    }
    r.update(kw)
    return r


def full_md(date, extra=""):
    body = "\n\n".join(f"{s}\n\n" + "내용 " * 60 for s in dd.REQUIRED_SECTIONS)
    return f"# 급락 국면 종합 {date}\n\n{body}\n{extra}"


class DetectTest(unittest.TestCase):
    def test_counts_market_and_daily_hits_in_window(self):
        rs = [
            report("a", "2026-10-15", text="코스피 급락에 매도 사이드카 발동"),
            report("b", "2026-10-14", kind="daily_series", text="외국인 투매"),
            report("c", "2026-10-14", text="지수 폭락"),
            report("old", "2026-10-12", text="사이드카"),  # 기간 밖
        ]
        hits = dd.detect(rs, "2026-10-15", CFG)
        self.assertEqual({h["report_id"] for h in hits}, {"a", "b", "c"})
        self.assertTrue(dd.triggered(hits, CFG))

    def test_ignores_company_reports_and_unsummarized(self):
        rs = [
            report("co", "2026-10-15", desk="산업·기업", text="주가 급락, 사이드카"),
            report("raw", "2026-10-15", text="사이드카") | {"summary": None},
            report("ok", "2026-10-15", text="평온한 장세"),
        ]
        self.assertEqual(dd.detect(rs, "2026-10-15", CFG), [])

    def test_single_stock_drop_is_not_a_signal(self):
        rs = [report("x", "2026-10-15", text="에이피알 주가 급락")]
        self.assertEqual(dd.detect(rs, "2026-10-15", CFG), [])


class SelectTest(unittest.TestCase):
    def test_filters_irrelevant_market_cards(self):
        rs = [
            report("rel", "2026-10-15", text="코스피 외국인 순매도, 환율 하락, 반도체 약세"),
            report("esg", "2026-10-15", text="도시 광산 ESG 동향"),
            report("ind", "2026-10-14", desk="산업·기업", text="반도체 메모리 환율 역풍 외국인 매도"),
            report("ind2", "2026-10-14", desk="산업·기업", text="화장품 신제품 출시"),
            report("d", "2026-10-15", kind="daily_series", text="아무 내용"),
        ]
        sel = dd.select(rs, "2026-10-15", CFG)
        self.assertEqual([r["report_id"] for r in sel["market"]], ["rel"])
        self.assertEqual([r["report_id"] for r in sel["industry"]], ["ind"])
        self.assertEqual([r["report_id"] for r in sel["daily"]], ["d"])

    def test_window_and_newest_first(self):
        text = "코스피 외국인 순매도 환율"
        rs = [report("a", "2026-10-11", text=text), report("b", "2026-10-15", text=text),
              report("c", "2026-10-10", text=text)]
        sel = dd.select(rs, "2026-10-15", CFG)
        self.assertEqual([r["report_id"] for r in sel["market"]], ["b", "a"])


class ValidateTest(unittest.TestCase):
    def test_accepts_and_strips_preamble_and_fence(self):
        md = "```markdown\n좋습니다.\n" + full_md("2026-10-15") + "\n```"
        out = dd.validate(md, "2026-10-15")
        self.assertTrue(out.startswith("# 급락 국면 종합 2026-10-15"))

    def test_rejects_missing_section(self):
        md = full_md("2026-10-15").replace("## 두 가설", "## 가설")
        with self.assertRaisesRegex(LLMError, "두 가설"):
            dd.validate(md, "2026-10-15")

    def test_rejects_wrong_title(self):
        with self.assertRaisesRegex(LLMError, "제목"):
            dd.validate(full_md("2026-10-14"), "2026-10-15")


class PreviousJudgmentTest(unittest.TestCase):
    def test_picks_latest_earlier_file_within_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "2026-08-01.md").write_text(full_md("2026-08-01"), encoding="utf-8")
            (d / "2026-10-13.md").write_text(
                full_md("2026-10-13").replace(dd.JUDGMENT_SECTION + "\n\n", dd.JUDGMENT_SECTION + "\n\n반증: 외국인 4주 순매도\n"),
                encoding="utf-8",
            )
            (d / "2026-10-16.md").write_text(full_md("2026-10-16"), encoding="utf-8")  # 대상일 이후
            name, text = dd.previous_judgment("2026-10-15", CFG, out_dir=d)
            self.assertEqual(name, "2026-10-13")
            self.assertIn("외국인 4주 순매도", text)

    def test_none_when_too_old(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "2026-01-01.md").write_text(full_md("2026-01-01"), encoding="utf-8")
            self.assertIsNone(dd.previous_judgment("2026-10-15", CFG, out_dir=d))


class DayRangeTest(unittest.TestCase):
    def test_inclusive_oldest_first(self):
        self.assertEqual(dd.day_range("2026-10-01", 3), ["2026-09-29", "2026-09-30", "2026-10-01"])


if __name__ == "__main__":
    unittest.main()
