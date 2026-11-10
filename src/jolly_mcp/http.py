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


_PROFILES = ("chrome120", "chrome131", "safari17_0")
_MAX_ATTEMPTS = 2  # one retry with the next profile
_RETRY_BACKOFF = 1.0  # seconds between attempts
_profile_idx = 0  # sticky: profile that last succeeded


def _new_session() -> _r.Session:
    """Fresh session with the sticky profile (chrome120 on a fresh process)."""
    return _r.Session(impersonate=_PROFILES[_profile_idx % len(_PROFILES)])


def _session() -> _r.Session:
    return _new_session()


def _reprime(listing_url: str) -> _r.Session:
    """New session with the next profile + fresh listing-page cookies."""
    global _profile_idx
    _profile_idx = (_profile_idx + 1) % len(_PROFILES)
    s = _new_session()
    try:
        s.get(listing_url, headers=_HEADERS_HTML, timeout=60)
    except Exception:
        pass  # the POST retry below reports the real failure
    return s


def _request(url: str, headers: dict, timeout: float = TIMEOUT):
    """Stateless GET with fingerprint rotation (detail/campaign pages)."""
    global _profile_idx
    last_exc: Exception | None = None
    for k in range(_MAX_ATTEMPTS):
        profile = _PROFILES[(_profile_idx + k) % len(_PROFILES)]
        try:
            resp = _r.get(url, impersonate=profile, headers=headers, timeout=timeout)
        except Exception as e:
            last_exc = e
            if k + 1 < _MAX_ATTEMPTS:
                time.sleep(_RETRY_BACKOFF)
                continue
            raise JollyError(f"network error fetching {url}: {e}") from e
        if resp.status_code in (403, 429):
            if k + 1 < _MAX_ATTEMPTS:
                time.sleep(_RETRY_BACKOFF)
                continue
            return resp
        _profile_idx = (_profile_idx + k) % len(_PROFILES)
        return resp
    raise JollyError(f"network error fetching {url}: {last_exc}") from last_exc


def fetch_listing_page(city_slug: str) -> tuple[_r.Session, str]:
    """GET /{city}-otelleri; returns the session (with cookies) + HTML.

    Retries once with the next fingerprint profile on HTTP 403/429 or a
    transport error.
    """
    global _profile_idx
    url = f"{BASE}/{city_slug}-otelleri"
    last_exc: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        s = _new_session()
        try:
            resp = s.get(url, headers=_HEADERS_HTML, timeout=60)
        except Exception as e:
            last_exc = e
            if attempt + 1 < _MAX_ATTEMPTS:
                _profile_idx = (_profile_idx + 1) % len(_PROFILES)
                time.sleep(_RETRY_BACKOFF)
                continue
            raise JollyError(f"network error fetching {url}: {e}") from e
        if resp.status_code in (403, 429):
            if attempt + 1 < _MAX_ATTEMPTS:
                _profile_idx = (_profile_idx + 1) % len(_PROFILES)
                time.sleep(_RETRY_BACKOFF)
                continue
            if resp.status_code == 403:
                raise JollyError(
                    "jollytur.com refused the request (HTTP 403, bot wall) — try again later"
                )
            raise JollyError(
                "jollytur.com rate-limited the request (HTTP 429) — try again later"
            )
        if resp.status_code == 404:
            raise JollyError(f"no Jolly hotel listing for city {city_slug!r} (HTTP 404)")
        if resp.status_code != 200:
            raise JollyError(f"Jolly returned HTTP {resp.status_code} for {url}")
        return s, resp.text
    raise JollyError(f"network error fetching {url}: {last_exc}") from last_exc


def search_hotels_raw(
    session: _r.Session, listing_url: str, form: dict, page: int = 1
) -> dict:
    """POST /hotel/GetListPagePartials with the listing form + filters.

    Retries once on timeout or HTTP 403/429 with the next fingerprint
    profile; a rotated session re-GETs the listing page first so its
    cookies (CustomerTrackId, .JollyB2C.Session) are fresh.
    """
    url = f"{BASE}/hotel/GetListPagePartials?hrq={_hrq(form)}"
    headers = dict(_HEADERS_POST)
    headers["Referer"] = listing_url
    last: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            resp = session.post(url, headers=headers, data=form, timeout=TIMEOUT)
        except Exception as e:
            last = e
            if attempt + 1 < _MAX_ATTEMPTS:
                session = _reprime(listing_url)
                time.sleep(5)
                continue
            raise JollyError(f"Jolly search timed out after 2 attempts: {last}")
        if resp.status_code in (403, 429):
            if attempt + 1 < _MAX_ATTEMPTS:
                session = _reprime(listing_url)
                time.sleep(_RETRY_BACKOFF)
                continue
            if resp.status_code == 403:
                raise JollyError(
                    "jollytur.com refused the request (HTTP 403, bot wall) — try again later"
                )
            raise JollyError(
                "jollytur.com rate-limited the request (HTTP 429) — try again later"
            )
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
        resp = _request(url, _HEADERS_HTML, 60)
    except Exception as e:
        raise JollyError(f"network error fetching {url}: {e}") from e
    if resp.status_code == 403:
        raise JollyError(
            "jollytur.com refused the request (HTTP 403, bot wall) — try again later"
        )
    if resp.status_code == 429:
        raise JollyError(
            "jollytur.com rate-limited the request (HTTP 429) — try again later"
        )
    if resp.status_code == 404:
        raise JollyError(f"no Jolly hotel page for {slug!r} (HTTP 404)")
    if resp.status_code != 200:
        raise JollyError(f"Jolly returned HTTP {resp.status_code} for {url}")
    return resp.text


def fetch_campaigns() -> str:
    """GET /kampanyalar."""
    url = f"{BASE}/kampanyalar"
    try:
        resp = _request(url, _HEADERS_HTML, 60)
    except Exception as e:
        raise JollyError(f"network error fetching {url}: {e}") from e
    if resp.status_code == 403:
        raise JollyError(
            "jollytur.com refused the request (HTTP 403, bot wall) — try again later"
        )
    if resp.status_code == 429:
        raise JollyError(
            "jollytur.com rate-limited the request (HTTP 429) — try again later"
        )
    if resp.status_code != 200:
        raise JollyError(f"Jolly returned HTTP {resp.status_code} for {url}")
    return resp.text


def fetch_home_html() -> str:
    """Homepage HTML (used by health_check)."""
    resp = _request(f"{BASE}/", _HEADERS_HTML, 60)
    if resp.status_code == 403:
        raise JollyError(
            "jollytur.com refused the request (HTTP 403, bot wall) — try again later"
        )
    if resp.status_code == 429:
        raise JollyError(
            "jollytur.com rate-limited the request (HTTP 429) — try again later"
        )
    if resp.status_code != 200:
        raise JollyError(f"Jolly returned HTTP {resp.status_code} for {BASE}/")
    return resp.text


def health_check() -> dict:
    """One polite probe of the source site.

    Returns {"status": "ok"|"blocked"|"error", "http_status": int|None,
    "url": ..., "detail": ...}. Used by the `jolly_health` tool
    and the daily smoke CI. Added 2026-11-10 (fleet audit fix).
    """
    url = "https://www.jollytur.com/"
    try:
        fetch_home_html()
    except JollyError as e:
        msg = str(e)
        if "403" in msg:
            return {"status": "blocked", "http_status": 403, "url": url, "detail": msg}
        if "429" in msg:
            return {"status": "blocked", "http_status": 429, "url": url, "detail": msg}
        return {"status": "error", "http_status": None, "url": url, "detail": msg}
    return {"status": "ok", "http_status": 200, "url": url}
