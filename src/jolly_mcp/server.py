"""MCP server: unofficial read-only access to Jolly Tur hotels (jollytur.com)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
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
Built by Mohammad Abbasi (mohammad-abbasi-sh) — https://almanibama.ir · https://mabbasi.ir
"""


_SOURCE = "jollytur.com"
_DISCLAIMER = "Unofficial read-only data from jollytur.com; verify on the site before acting on it."


def _envelope() -> dict:
    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": _SOURCE,
        "disclaimer": _DISCLAIMER,
    }


def _ok(payload: dict) -> str:
    return json.dumps({**_envelope(), **payload}, ensure_ascii=False)


def _err(e: Exception) -> str:
    return _ok({"error": str(e)})


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
        return _ok(_h.parse_search_result(payload, check_in, check_out))
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
        return _ok(_h.parse_hotel_detail(html_text, url))
    except (_http.JollyError, ValueError) as e:
        return _err(e)


@mcp.tool()
def jolly_list_campaigns() -> str:
    """Current Jolly Tur campaigns from /kampanyalar (title + link)."""
    try:
        camps = _h.parse_campaigns(_http.fetch_campaigns())
        return _ok({"count": len(camps), "campaigns": camps})
    except (_http.JollyError, ValueError) as e:
        return _err(e)


@mcp.tool()
def jolly_health() -> str:
    """Check whether jollytur.com is reachable right now.

    Returns status ok (HTTP 200), blocked (HTTP 403/429 — bot wall or
    rate limit) or error, plus the HTTP status and the probed URL.
    One polite request; it does not fetch any listings."""
    return _ok(_http.health_check())


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    sys.exit(main())
