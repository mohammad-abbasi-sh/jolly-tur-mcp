"""MCP server: unofficial read-only access to Jolly Tur hotels (jollytur.com)."""
from __future__ import annotations

import json
import sys

from mcp.server.fastmcp import FastMCP

from . import hotels as _h
from . import http as _http

mcp = FastMCP("jolly-tur-mcp")

INSTRUCTIONS = """\
Unofficial read-only MCP server for Jolly Tur (jollytur.com), one of \
Türkiye's top-3 tour operators — hotel search with live prices, hotel \
detail and current campaigns, from the site's own listing/search flow. \
No login, no API key, read-only. Prices are in Turkish Lira (TRY) for \
the requested stay; prices only exist when check-in/check-out dates are \
given (without dates the cards show no price). Searches are slow \
(~10-15s: the site renders results server-side per query), so prefer \
one search per question. City is a Turkish slug, e.g. "antalya", \
"istanbul", "izmir", "bodrum". Built by Mohammad Abbasi \
(github.com/mohammad-abbasi-sh/jolly-tur-mcp).\
"""


def _err(e: Exception) -> str:
    return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def jolly_search_hotels(
    city: str, check_in: str = "", check_out: str = "", page: int = 1, hotel_name: str = ""
) -> str:
    """Search Jolly hotels in a city. city: slug like "antalya", "istanbul", \
"bodrum". check_in/check_out: YYYY-MM-DD (both needed for prices). \
page: results page (20 hotels/page). hotel_name: optional name filter \
(4+ chars). Returns hotels with rating, concept, campaigns and prices."""
    slug = city.strip().lower().replace(" ", "-")
    try:
        session, listing_html = _http.fetch_listing_page(slug)
        form = _h.parse_search_form(listing_html)
        post = _h.build_search_post(form, check_in, check_out, page, hotel_name)
        payload = _http.search_hotels_raw(
            session, f"https://www.jollytur.com/{slug}-otelleri", post, page
        )
        return json.dumps(
            _h.parse_search_result(payload, check_in, check_out), ensure_ascii=False
        )
    except (_http.JollyError, ValueError) as e:
        return _err(e)


@mcp.tool()
def jolly_get_hotel(hotel_slug: str) -> str:
    """Detail for one Jolly hotel. hotel_slug: e.g. "the-x-belek" (from \
search results) or a full jollytur.com hotel URL."""
    try:
        html_text = _http.fetch_hotel_detail(hotel_slug)
        url = (
            hotel_slug
            if hotel_slug.startswith("http")
            else f"https://www.jollytur.com/{hotel_slug.strip('/')}"
        )
        return json.dumps(_h.parse_hotel_detail(html_text, url), ensure_ascii=False)
    except (_http.JollyError, ValueError) as e:
        return _err(e)


@mcp.tool()
def jolly_list_campaigns() -> str:
    """Current Jolly Tur campaigns from /kampanyalar (title + link)."""
    try:
        camps = _h.parse_campaigns(_http.fetch_campaigns())
        return json.dumps({"count": len(camps), "campaigns": camps}, ensure_ascii=False)
    except (_http.JollyError, ValueError) as e:
        return _err(e)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    sys.exit(main())
