import unittest
from datetime import date

from scripts.collectors.base import ReportType
from scripts.collectors.hankyung import HankyungCollector
from scripts.collectors.mirae import MiraeCollector, classify
from scripts.estimates import extract_generic
from scripts import signals as sg

# 한경 컨센서스 목록 (2026-10-14 실측 구조를 줄인 것)
HK_BUSINESS = """<table><thead><tr><th>작성일</th><th>제목</th><th>적정가격</th><th>투자의견</th><th>작성자</th>
<th>제공출처</th><th>기업정보</th><th>차트</th><th>첨부파일</th></tr></thead><tbody>
<tr><td>2026-10-14</td><td class="text_l"><a href="/analysis/downpdf?report_idx=652953">한국콜마(161890) 계절성을 뛰어넘는 업황</a>
<div class="layerPop"><div class="pop01"><strong>한국콜마(161890) 계절성을 뛰어넘는 업황</strong><ul><li>계절성을 뛰어넘는 업황</li></ul></div></div></td>
<td>180,000</td><td>매수</td><td>형권훈</td><td>SK증권</td><td></td><td></td>
<td><a href="/analysis/downpdf?report_idx=652953" title="2026_ko.pdf">pdf</a></td></tr>
<tr><td>2026-10-14</td><td class="text_l"><a href="/analysis/downpdf?report_idx=652900">하나 리포트(000000) 제외 대상</a></td>
<td>1,000</td><td>매수</td><td>누구</td><td>하나증권</td><td></td><td></td><td></td></tr>
</tbody></table>"""

HK_MARKET = """<table><thead><tr><th>작성일</th><th>제목</th><th>작성자</th><th>제공출처</th><th>차트</th><th>첨부파일</th></tr></thead><tbody>
<tr><td>2026-10-14</td><td><a href="/analysis/downpdf?report_idx=652960">Morning Meeting 10/14</a></td><td>홍길동</td><td>유안타증권</td><td></td><td></td></tr>
</tbody></table>"""

MIRAE_LIST = """<table><tbody>
<tr><td>2026-10-14</td><td><div class="subject"><a href="javascript:view('2343355','2589')"><b>휴젤 (145020/매수)</b><br/>3Q26 Preview: 단기 실적 눈높이 조정</a></div></td>
<td><a href="javascript:downConfirm('https://securities.miraeasset.com/bbs/download/2147829.pdf?attachmentId=2147829','2147829','1024','768','yes','yes');" title="20261014_휴젤.pdf(새창열림)">f</a></td><td>서미화</td></tr>
<tr><td>2026-10-14</td><td><div class="subject"><a href="javascript:view('2343364','2591')"><b>마켓 뷰(10월 14일)</b><br/>반등, 강도가 문제</a></div></td>
<td></td><td>김주연</td></tr>
</tbody></table>"""


class HankyungTest(unittest.TestCase):
    def setUp(self):
        self.c = HankyungCollector(exclude_brokers=["하나증권"], today=date(2026, 10, 14))

    def test_business_row(self):
        items, rows = self.c.parse_list_page(HK_BUSINESS, "business")
        self.assertEqual(rows, 2)  # 제외 증권사도 행 수에는 센다 (마지막 페이지 판정용)
        self.assertEqual(len(items), 1)
        it = items[0]
        self.assertEqual((it.report_id, it.broker, it.stock_code, it.list_rating, it.list_target_price),
                         ("hk_652953", "SK증권", "161890", "매수", 180000.0))
        self.assertEqual(it.category, "기업분석")
        self.assertEqual(it.title, "한국콜마(161890) 계절성을 뛰어넘는 업황")
        self.assertEqual(it.preview_text, "계절성을 뛰어넘는 업황")
        self.assertTrue(it.pdf_url.endswith("report_idx=652953"))

    def test_columns_found_by_header_name(self):
        items, _ = self.c.parse_list_page(HK_MARKET, "market")
        it = items[0]
        self.assertEqual((it.broker, it.analyst, it.list_target_price), ("유안타증권", "홍길동", None))
        self.assertEqual(it.report_type, ReportType.DAILY_SERIES)


class MiraeTest(unittest.TestCase):
    def test_list(self):
        items = MiraeCollector().parse_list_page(MIRAE_LIST)
        a, b = items
        self.assertEqual((a.report_id, a.broker, a.stock_code, a.list_rating, a.category),
                         ("mirae_2343355", "미래에셋증권", "145020", "매수", "기업분석"))
        self.assertEqual(a.title, "휴젤 (145020/매수): 3Q26 Preview: 단기 실적 눈높이 조정")
        self.assertIn("2147829.pdf", a.pdf_url)
        self.assertEqual(b.report_type, ReportType.DAILY_SERIES)
        self.assertIsNone(b.pdf_url)

    def test_classify(self):
        self.assertEqual(classify("중국 반도체 (비중확대/유지)")[0], "산업분석")
        self.assertEqual(classify("유나이티드 헬스 그룹 (UNH US/Not Rated)")[0], "글로벌 기업분석")
        self.assertEqual(classify("Market Issue")[0], "투자전략")


def generic(text, **kw):
    r = {"report_id": "hk_1", "published_date": "2026-10-14", "title": kw.pop("title", "팬오션(028670) 테스트"),
         "pdf_text": text, "broker": kw.pop("broker", "iM증권"), "report_type": "individual"}
    r.update(kw)
    return extract_generic(r)


class GenericParseTest(unittest.TestCase):
    def test_prev_target_from_sentence(self):
        o = generic("투자의견 Buy 유지, 목표주가 8,500원으로 상향\n팬오션에 대해 목표주가를 기존 8,000원에서 8,500원으로 상향한다.\n"
                    "Buy (Maintain)\n목표주가(12M) 8,500원(상향)\n종가(2026.10.13) 6,030원")
        self.assertEqual((o.code, o.rating, o.target_price, o.prev_target_price, o.price), ("028670", "매수", 8500, 8000, 6030))

    def test_man_won_and_list_values_win(self):
        o = generic("목표주가를 28만원(기존 35만원)으로 하향한다.\n투자의견(유지) 매수\n목표주가(하향) ▼ 280,000원\n현재주가(26/10/13) 169,900원",
                    title="휴젤 (145020/매수): x", broker="미래에셋증권", stock_code="145020")
        self.assertEqual((o.target_price, o.tp_status, o.prev_target_price, o.price), (280000, "하향", 350000, 169900))
        o = generic("목표주가: 1,000 원", list_target_price=180000.0, list_rating="Buy", stock_code="161890")
        self.assertEqual((o.target_price, o.rating), (180000.0, "매수"))

    def test_comparison_table(self):
        o = generic("현재 직전 변동\n투자의견 BUY BUY -\n목표주가 530,000 470,000 ▲\n", list_target_price=530000.0)
        self.assertEqual(o.prev_target_price, 470000)

    def test_no_code_no_observation(self):
        self.assertIsNone(generic("목표주가 10,000원", title="Weekly Amazon Beauty Check"))


class MultiBrokerSignalTest(unittest.TestCase):
    CFG = {"tp_valid_days": 180, "wave_days": 30, "wave_min_brokers": 3}

    def pt(self, d, b, tp, rating="매수", rid=None):
        return {"date": d, "broker": b, "target_price": tp, "rating": rating, "report_id": rid}

    def test_consensus_ignores_new_coverage_and_measures_revisions(self):
        tl = [self.pt("2026-09-01", "A", 100), self.pt("2026-09-02", "B", 120),
              self.pt("2026-09-10", "C", 200),           # 신규 커버: 평균은 바뀌어도 '조정'은 아님
              self.pt("2026-10-01", "A", 110, rid="r1")]  # 기존 증권사 조정
        series, changes, _ = sg.tp_consensus(tl, [], self.CFG)
        self.assertEqual([s["n"] for s in series], [1, 2, 3, 3])
        self.assertEqual(len(changes), 1)
        c = changes[0]
        self.assertEqual((c["date"], c["n"], c["brokers"], c["report_id"]), ("2026-10-01", 3, ["A"], "r1"))
        self.assertAlmostEqual(c["pct"], round(10 / 3 / (420 / 3) * 100, 1))

    def test_stale_target_drops_out(self):
        tl = [self.pt("2026-01-01", "A", 100), self.pt("2026-09-01", "B", 120)]
        series, _, _ = sg.tp_consensus(tl, [], self.CFG)
        self.assertEqual(series[-1]["n"], 1)  # A는 180일이 지나 빠진다

    def test_wave(self):
        ch = lambda d, b, p: {"date": d, "broker": b, "tp_pct": p, "report_id": f"{b}{d}"}  # noqa: E731
        moves = [ch("2026-10-01", "A", -10), ch("2026-10-05", "B", -5), ch("2026-10-09", "C", -8)]
        _, _, waves = sg.tp_consensus([], moves, self.CFG)
        self.assertEqual(len(waves), 1)
        self.assertEqual((waves[0]["date"], waves[0]["direction"], waves[0]["brokers"]), ("2026-10-09", -1, ["A", "B", "C"]))
        # 반대 방향이 섞이면 물결이 아니다
        _, _, waves = sg.tp_consensus([], moves + [ch("2026-10-03", "D", 5)], self.CFG)
        self.assertEqual(waves, [])

    def test_prev_hint_change_without_history(self):
        tl = [{"date": "2026-10-14", "broker": "IBK", "rating": "매수", "target_price": 13000, "report_id": "x"}]
        ch = sg.rating_changes(tl, [], {"2026-10-14": 17000})
        self.assertEqual((ch[0]["tp_from"], ch[0]["tp_pct"], ch[0]["days"]), (17000, -23.5, None))


if __name__ == "__main__":
    unittest.main()
