"""Offline tests — parse real captured Jolly Tur pages, no network."""
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from jolly_mcp import hotels

FIX = pathlib.Path(__file__).resolve().parent / "fixtures"


class TestSearchForm(unittest.TestCase):
    def test_form_parsed(self):
        form = hotels.parse_search_form(
            (FIX / "antalya_listing.html").read_text(encoding="utf-8")
        )
        self.assertEqual(form["SearchParameters.Id"], "38140")
        self.assertEqual(form["SearchParameters.SearchType"], "Location")
        self.assertEqual(form["SearchParameters.HotelType"], "Domestic")
        self.assertEqual(form["SearchParameters.RequestPath"], "/antalya-otelleri")
        self.assertEqual(form["SearchParameters.DefaultFilterValue"], "38140-Ci")

    def test_build_post(self):
        form = hotels.parse_search_form(
            (FIX / "antalya_listing.html").read_text(encoding="utf-8")
        )
        post = hotels.build_search_post(form, "2026-11-20", "2026-11-22", 1)
        self.assertEqual(post["SearchParameters.StartDate"], "20.11.2026")
        self.assertEqual(post["SearchParameters.EndDate"], "22.11.2026")
        self.assertEqual(post["filters"], "Location:38140-Ci")
        self.assertEqual(post["pageNo"], "1")
        self.assertEqual(post["rooms"], "1")

    def test_bad_date(self):
        form = {"SearchParameters.DefaultFilterValue": "38140-Ci"}
        with self.assertRaises(ValueError):
            hotels.build_search_post(form, "20/11/2026", "22.11.2026")


class TestSearchResult(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        payload = json.loads((FIX / "antalya_search.json").read_text(encoding="utf-8"))
        cls.parsed = hotels.parse_search_result(payload, "2026-11-20", "2026-11-22")

    def test_result_count(self):
        self.assertEqual(self.parsed["result_count"], 1067)
        self.assertEqual(self.parsed["count"], 20)
        self.assertTrue(self.parsed["prices_available"])

    def test_first_hotel(self):
        h = self.parsed["hotels"][0]
        self.assertEqual(h["name"], "The X Belek")
        self.assertEqual(h["slug"], "the-x-belek")
        self.assertEqual(h["location"], "Antalya, Serik, Belek, Kadriye")
        self.assertEqual(h["rating"], 9.6)
        self.assertEqual(h["rating_count"], 4186)
        self.assertEqual(h["rating_text"], "Mükemmel")
        self.assertEqual(h["concept"], "Ultra Her Şey Dahil")
        self.assertEqual(h["total_price_tl"], 21576.00)
        self.assertEqual(h["discounted_price_tl"], 13377.12)
        self.assertEqual(h["currency"], "TL")
        self.assertTrue(h["url"].endswith("/the-x-belek"))

    def test_all_have_names_and_urls(self):
        self.assertTrue(all(h["name"] and h["url"] for h in self.parsed["hotels"]))

    def test_some_have_prices(self):
        priced = [h for h in self.parsed["hotels"] if h["total_price_tl"]]
        self.assertGreater(len(priced), 15)


class TestHotelDetail(unittest.TestCase):
    def test_detail(self):
        d = hotels.parse_hotel_detail(
            (FIX / "hotel_detail.html").read_text(encoding="utf-8"),
            "https://www.jollytur.com/the-x-belek",
        )
        self.assertEqual(d["name"], "The X Belek")
        self.assertEqual(d["location"], "antalya")
        self.assertEqual(d["region"], "akdeniz bolgesi")
        self.assertEqual(d["concept"], "Ultra Her Şey Dahil")
        self.assertIn("Belek-Kadriye", d["about"])
        self.assertIn("399 oda", d["about"])


class TestCampaigns(unittest.TestCase):
    def test_campaigns(self):
        camps = hotels.parse_campaigns(
            (FIX / "kampanyalar.html").read_text(encoding="utf-8")
        )
        self.assertGreater(len(camps), 5)
        urls = [c["url"] for c in camps]
        self.assertEqual(len(urls), len(set(urls)))  # deduped
        titles = " | ".join(c["title"] for c in camps)
        self.assertIn("1 Gece Bizden", titles)
        self.assertIn("Şehir Otellerinde Erken Rezervasyon", titles)
        self.assertTrue(all(c["url"].startswith("https://www.jollytur.com/") for c in camps))


if __name__ == "__main__":
    unittest.main()
