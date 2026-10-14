import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import estimates as est
from scripts import signals as sg
from scripts.llm import LLMRateLimitError

# 하나증권 기업 리포트 원문 텍스트를 줄여서 흉내 낸 것 (pypdf 추출 결과의 모양 그대로)
COMPANY_TEXT = """2026년 10월 07일 I 기업분석
코스맥스 (192820)
계절성을 깨트리다
목표주가 30.5->38만원으로 상향 조정
실적 추정치 상향 조정에 따라 목표주가를 38만원으로 올린다.

 BUY (유지)
    목표주가(12M) 380,000원(상향)
 현재주가(10.06) 298,000원
 Key Data
 Consensus Data
  2026 2027
 매출액(십억원) 2,950.1 3,320.4
 영업이익(십억원) 260.2 301.5
 순이익(십억원) 180.0 210.0
 EPS(원) 15,800 18,188
 BPS(원) 90,000 100,000

Stock Price
 Financial Data (십억원, %, 배, 원)
 투자지표 2024 2025 2026F 2027F
 매출액 2,166.1 2,400.0 3,050.0 3,400.0
 영업이익 175.4 200.0 290.0 340.0
 순이익 100.0 120.0 200.0 240.0
 EPS 8,800 10,500 17,500 21,000
 증감율 10.0 19.3 66.7 20.0
Analyst 박종대
  코스맥스 (192820)
하나증권•4
 투자의견 변동 내역 및 목표주가 괴리율
   코스맥스
날짜 투자의견 목표주가 괴리율
평균 최고/최저
26.10.7 BUY 380,000
26.8.12 BUY 305,000 -20.00% -10.00%
26.3.2 BUY 250,000 -15.00% -5.00%
25.11.1 BUY 220,000 -12.00% -3.00%
25.4.16 담당자 변경  - -
24.10.4 Neutral 200,000 -10.08% 3.04%
 Compliance Notice
"""


def report(rid, date, title, text, **kw):
    r = {"report_id": rid, "report_type": "individual", "title": title, "published_date": date,
         "pdf_text": text, "industries": ["화장품"]}
    r.update(kw)
    return r


class ParseTest(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(est.parse_number("(2.0)"), -2.0)
        self.assertEqual(est.parse_number("1,234.5"), 1234.5)
        self.assertIsNone(est.parse_number("-"))
        self.assertIsNone(est.parse_number("적지"))
        self.assertIsNone(est.parse_number("N/A"))

    def test_title(self):
        t = est.parse_title("한미약품(128940.KS/BUY): 더 안정적인 성장")
        self.assertEqual((t["code"], t["market"], t["rating"]), ("128940", "KS", "매수"))
        self.assertEqual(est.parse_title("에이치브이엠 (295310.KQ): 수요 대응")["code"], "295310")
        self.assertIsNone(est.parse_title("[해외채권] 미국 기간 프리미엄"))

    def test_target_box(self):
        box = est.parse_target_boxes(COMPANY_TEXT)[0]
        self.assertEqual((box.rating, box.rating_status, box.target_price, box.tp_status, box.price),
                         ("매수", "유지", 380000, "상향", 298000))

    def test_financial_keeps_only_forecast_years(self):
        blk = est.parse_financial_blocks(COMPANY_TEXT)[0]
        self.assertEqual(blk.forecast_years, ["2026", "2027"])
        self.assertEqual(blk.values["2027"]["op"], 340.0)
        self.assertEqual(blk.values["2026"]["eps"], 17500)

    def test_financial_drops_profit_larger_than_revenue(self):
        text = ("Financial Data (십억원, %, 배, 원)\n 투자지표 2026F 2027F\n"
                " 매출액 10,794.4 11,229.1\n 영업이익 3,101.7 11,229.1\n")
        v = est.parse_financial_blocks(text)[0].values
        self.assertEqual(v["2026"]["op"], 3101.7)
        self.assertIsNone(v["2027"]["op"])

    def test_foreign_currency_table_skipped(self):
        self.assertEqual(est.parse_financial_blocks("Financial Data (백만 CNY)\n 투자지표 2026F\n 매출 1\n"), [])

    def test_consensus(self):
        c = est.parse_consensus_blocks(COMPANY_TEXT)[0]
        self.assertEqual(c.values["2027"]["eps"], 18188)

    def test_history_table(self):
        tbl = est.parse_history_tables(COMPANY_TEXT)[0]
        self.assertEqual(tbl.name, "코스맥스")
        self.assertEqual(tbl.rows[0].date, "2026-10-07")
        self.assertEqual(tbl.rows[0].target_price, 380000)
        self.assertEqual(tbl.rows[4].note, "담당자 변경")
        self.assertEqual(tbl.rows[5].rating, "중립")

    def test_body_code_beats_title_typo(self):
        r = report("hana_1", "2026-10-07", "코스맥스(192920.KS/매수): 계절성을 깨트리다", COMPANY_TEXT)
        obs, tables = est.extract(r, est.build_name_map([r]))
        self.assertEqual([o.code for o in obs], ["192820"])
        self.assertTrue(obs[0].primary)
        self.assertEqual(tables[0][0], "192820")

    def test_block_far_from_header_is_dropped(self):
        text = "회사A (111111)\n" + "가" * 4000 + "\n Consensus Data\n  2026 2027\n 영업이익(십억원) 100 120\n"
        obs, _ = est.extract(report("hana_2", "2026-10-01", "데일리", text, report_type="daily_series"), {})
        self.assertEqual(obs, [])


class EventTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [
            patch.object(sg, "STOCKS_DIR", root / "stocks"),
            patch.object(sg, "EVENTS_DIR", root / "events"),
            patch.object(sg, "SIGNALS_DIR", root / "signals"),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def build(self, reports):
        sg.build(reports)
        return [e for f in sorted(sg.EVENTS_DIR.glob("*.json")) for e in json.loads(f.read_text())]

    def test_tp_jump_and_streak_from_history_table(self):
        r = report("hana_1", "2026-10-07", "코스맥스(192820.KS/매수): 계절성을 깨트리다", COMPANY_TEXT)
        evs = self.build([r])
        types = {e["type"]: e for e in evs}
        self.assertIn("tp_up", types)  # 305,000 -> 380,000 (+24.6%)
        self.assertIn("+24.6%", types["tp_up"]["headline"])
        self.assertEqual(types["tp_up"]["report_id"], "hana_1")
        self.assertIn("tp_streak", types)  # 200k -> 220k -> 250k -> 305k -> 380k
        self.assertEqual(types["tp_streak"]["data"]["streak"], 4)
        # 수집 시작일 이전의 변경(2026-08-12 등)은 이벤트가 아니다
        self.assertTrue(all(e["date"] >= "2026-10-07" for e in evs))
        stock = json.loads((sg.STOCKS_DIR / "192820.json").read_text())
        self.assertEqual(stock["timeline"][-1]["target_price"], 380000)

    def test_estimate_revision_and_small_base(self):
        first = report("hana_1", "2026-09-01", "코스맥스(192820.KS/매수): 1", COMPANY_TEXT)
        second_text = COMPANY_TEXT.replace(" 영업이익 175.4 200.0 290.0 340.0", " 영업이익 175.4 200.0 250.0 345.0")
        second = report("hana_2", "2026-10-07", "코스맥스(192820.KS/매수): 2", second_text)
        evs = self.build([first, second])
        est_events = [e for e in evs if e["type"].startswith("est_")]
        self.assertEqual(len(est_events), 1)
        self.assertEqual(est_events[0]["type"], "est_down")  # 2026년 290 -> 250 (-13.8%)
        self.assertIn("-13.8%", est_events[0]["headline"])
        # 기저가 작은 지표(기준 미만)는 변화율을 계산하지 않는다
        ch = sg.series_changes(
            [est.Observation("1", "a", "r1", "2026-09-01", "t", "individual", True, estimates={"2027F": {"op": 0.2}}),
             est.Observation("1", "a", "r2", "2026-10-01", "t", "individual", True, estimates={"2027F": {"op": 1.2}})],
            "estimates", ("op",))
        self.assertIsNone(ch[0]["pct"])
        self.assertIsNone(ch[0]["turn"])

    def test_tp_maintained_in_text_is_not_an_event(self):
        # 본문은 "유지"인데 이력표 값과 다르면(수정주가 등) 이벤트를 내지 않는다
        text = COMPANY_TEXT.replace("380,000원(상향)", "381,000원(유지)").replace("26.10.7 BUY 380,000", "")
        r = report("hana_1", "2026-10-07", "코스맥스(192820.KS/매수): x", text)
        evs = self.build([r])
        self.assertFalse([e for e in evs if e["type"] == "tp_up"])

    def test_reason_survives_rebuild(self):
        r = report("hana_1", "2026-10-07", "코스맥스(192820.KS/매수): 계절성을 깨트리다", COMPANY_TEXT)
        evs = self.build([r])
        path = sg.EVENTS_DIR / "2026-10-07.json"
        data = json.loads(path.read_text())
        data[0]["reason"] = "실적 추정치 상향을 반영했다."
        data[0]["reason_checked"] = True
        path.write_text(json.dumps(data, ensure_ascii=False))
        evs = self.build([r])
        kept = [e for e in evs if e["id"] == data[0]["id"]][0]
        self.assertEqual(kept["reason"], "실적 추정치 상향을 반영했다.")

    def test_explain_events_fills_reason_and_stops_on_rate_limit(self):
        r = report("hana_1", "2026-10-07", "코스맥스(192820.KS/매수): 계절성을 깨트리다", COMPANY_TEXT)
        evs = self.build([r])
        tp_id = [e["id"] for e in evs if e["type"] == "tp_up"][0]
        with patch.object(sg, "load_reports", return_value=[r]), \
                patch("scripts.llm.ask_json", return_value={"reasons": {tp_id: "실적 추정치 상향을 반영했다."}}):
            done, aborted = sg.explain_events(5)
        self.assertEqual((done, aborted), (1, False))
        saved = {e["id"]: e for e in json.loads((sg.EVENTS_DIR / "2026-10-07.json").read_text())}
        self.assertEqual(saved[tp_id]["reason"], "실적 추정치 상향을 반영했다.")
        self.assertTrue(all(e.get("reason_checked") for e in saved.values() if e["report_id"] == "hana_1"
                            and not e["type"].startswith("gap_")))
        # 이미 확인한 이벤트는 다시 묻지 않는다
        with patch.object(sg, "load_reports", return_value=[r]), \
                patch("scripts.llm.ask_json", side_effect=LLMRateLimitError("429")) as ask:
            done, aborted = sg.explain_events(5)
        ask.assert_not_called()
        self.assertEqual((done, aborted), (0, False))


if __name__ == "__main__":
    unittest.main()
