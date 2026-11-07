"""Live tests — hit the real jollytur.com. Cautious: 4 requests, then stop.
Jolly searches are slow (~10-15s each) and the dated search occasionally
stalls (the server retries once).

Run:  pytest tests/test_live.py -v
Skip: pytest -m "not live"  (or set JOLLY_SKIP_LIVE=1)
"""
import os
import pathlib
import sys
import time
import unittest

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from jolly_mcp import hotels as _h
from jolly_mcp import http as _http

pytestmark = pytest.mark.live
SKIP = os.environ.get("JOLLY_SKIP_LIVE") == "1"


def _search(city, check_in="", check_out=""):
    session, listing_html = _http.fetch_listing_page(city)
    form = _h.parse_search_form(listing_html)
    post = _h.build_search_post(form, check_in, check_out, 1)
    payload = _http.search_hotels_raw(
        session, f"https://www.jollytur.com/{city}-otelleri", post, 1
    )
    return _h.parse_search_result(payload, check_in, check_out)


@pytest.mark.skipif(SKIP, reason="JOLLY_SKIP_LIVE=1")
class TestLive(unittest.TestCase):
    def test_search_undated_is_real(self):
        res = _search("antalya")
        self.assertGreater(res["result_count"], 1000)
        self.assertEqual(len(res["hotels"]), 20)
        self.assertFalse(res["prices_available"])
        print(f"\nLIVE Antalya undated: {res['result_count']} hotels, "
              f"first: {res['hotels'][0]['name']} "
              f"rating {res['hotels'][0]['rating']}")
        time.sleep(1)

    def test_search_dated_has_prices(self):
        res = _search("antalya", "2026-11-20", "2026-11-22")
        self.assertGreater(res["result_count"], 1000)
        priced = [h for h in res["hotels"] if h["total_price_tl"]]
        self.assertGreater(len(priced), 10)
        first = res["hotels"][0]
        print(f"\nLIVE Antalya 20-22 Nov: {first['name']} "
              f"{first['total_price_tl']} TL "
              f"(discounted {first['discounted_price_tl']} TL)")
        time.sleep(1)

    def test_hotel_detail_is_real(self):
        d = _h.parse_hotel_detail(
            _http.fetch_hotel_detail("the-x-belek"),
            "https://www.jollytur.com/the-x-belek",
        )
        self.assertEqual(d["name"], "The X Belek")
        self.assertEqual(d["concept"], "Ultra Her Şey Dahil")
        time.sleep(1)

    def test_campaigns_are_real(self):
        camps = _h.parse_campaigns(_http.fetch_campaigns())
        self.assertGreater(len(camps), 5)
        print(f"\nLIVE campaigns: {len(camps)}, e.g. {camps[0]['title']}")
