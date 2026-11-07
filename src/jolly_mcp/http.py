"""HTTP layer for jolly_mcp.

Jolly Tur (jollytur.com), one of Türkiye's top-3 tour operators, serves
hotel listing pages as an HTML shell — the real results come from a POST
to /hotel/GetListPagePartials with the search form's hidden
SearchParameters.* inputs (scraped from the listing page) plus an MD5
``hrq`` query token (md5 of the JSON array [Id, SearchType, HotelType,
RequestPath]) when no dates/filters are set. The POST needs the session
cookies the listing page sets (CustomerTrackId, .JollyB2C.Session), so
every search first GETs the listing page in one session, then POSTs.
Verified live 2026-11-07: listing + partials POST return 200 (undated
~10s, dated ~13s); the endpoint is slow and occasionally stalls, so the
POST is retried once on timeout. No login, no API key, read-only.
Hotel detail pages and /kampanyalar are plain server-rendered GETs.
"""
from __future__ import annotations

import hashlib
import json
import time

from curl_cffi import requests as _r

BASE = "https://www.jollytur.com"
TIMEOUT = 120.0

_HEADERS_HTML = {
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
_HEADERS_POST = {
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}


class JollyError(RuntimeError):
    pass


def _hrq(params: dict) -> str:
    arr = [
        params.get("SearchParameters.Id", ""),
        params.get("SearchParameters.SearchType", ""),
        params.get("SearchParameters.HotelType", ""),
        params.get("SearchParameters.RequestPath", ""),
    ]
    return hashlib.md5(json.dumps(arr, separators=(",", ":")).encode()).hexdigest()


def _session() -> _r.Session:
    return _r.Session(impersonate="chrome120")


def fetch_listing_page(city_slug: str) -> tuple[_r.Session, str]:
    """GET /{city}-otelleri; returns the session (with cookies) + HTML."""
    s = _session()
    url = f"{BASE}/{city_slug}-otelleri"
    try:
        resp = s.get(url, headers=_HEADERS_HTML, timeout=60)
    except Exception as e:
        raise JollyError(f"network error fetching {url}: {e}") from e
    if resp.status_code == 404:
        raise JollyError(f"no Jolly hotel listing for city {city_slug!r} (HTTP 404)")
    if resp.status_code != 200:
        raise JollyError(f"Jolly returned HTTP {resp.status_code} for {url}")
    return s, resp.text


def search_hotels_raw(
    session: _r.Session, listing_url: str, form: dict, page: int = 1
) -> dict:
    """POST /hotel/GetListPagePartials with the listing form + filters.
    Retries once on timeout (the endpoint occasionally stalls)."""
    url = f"{BASE}/hotel/GetListPagePartials?hrq={_hrq(form)}"
    headers = dict(_HEADERS_POST)
    headers["Referer"] = listing_url
    last: Exception | None = None
    for attempt in range(2):
        try:
            resp = session.post(url, headers=headers, data=form, timeout=TIMEOUT)
        except Exception as e:
            last = e
            time.sleep(5)
            continue
        if resp.status_code != 200:
            raise JollyError(f"Jolly search returned HTTP {resp.status_code} for {url}")
        try:
            return resp.json()
        except ValueError as e:
            raise JollyError("Jolly search returned non-JSON") from e
    raise JollyError(f"Jolly search timed out after 2 attempts: {last}")


def fetch_hotel_detail(slug: str) -> str:
    """GET a hotel detail page (slug or full URL)."""
    path = slug.strip()
    if path.startswith("http"):
        url = path
    else:
        url = f"{BASE}/{path.strip('/')}"
    try:
        resp = _r.get(url, impersonate="chrome120", headers=_HEADERS_HTML, timeout=60)
    except Exception as e:
        raise JollyError(f"network error fetching {url}: {e}") from e
    if resp.status_code == 404:
        raise JollyError(f"no Jolly hotel page for {slug!r} (HTTP 404)")
    if resp.status_code != 200:
        raise JollyError(f"Jolly returned HTTP {resp.status_code} for {url}")
    return resp.text


def fetch_campaigns() -> str:
    """GET /kampanyalar."""
    url = f"{BASE}/kampanyalar"
    try:
        resp = _r.get(url, impersonate="chrome120", headers=_HEADERS_HTML, timeout=60)
    except Exception as e:
        raise JollyError(f"network error fetching {url}: {e}") from e
    if resp.status_code != 200:
        raise JollyError(f"Jolly returned HTTP {resp.status_code} for {url}")
    return resp.text
