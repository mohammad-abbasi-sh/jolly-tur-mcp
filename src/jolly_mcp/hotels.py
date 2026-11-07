"""Domain logic: parse Jolly Tur listing/search HTML + detail pages (stdlib only).

Prices in search cards are Turkish-formatted strings in data attributes
("21.576,00" / "21576,00" -> 21576.00 TRY) and are only present when the
search has dates; without dates the cards show a "pick dates" prompt and
data-totalprice is 0. Rating is the "product-point" badge ("9,6") with a
"(4186 Değerlendirme)" count.
"""
from __future__ import annotations

import html
import re

BASE = "https://www.jollytur.com"

CONCEPTS = [
    "Ultra Her Şey Dahil",
    "Her Şey Dahil",
    "Yarım Pansiyon",
    "Tam Pansiyon",
    "Oda Kahvaltı",
    "Sadece Oda",
]


def _clean(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _price_tr(value: str | None) -> float | None:
    """Turkish number ("21.576,00", "21576,00", "0") -> float TRY or None."""
    if value is None:
        return None
    value = value.strip().replace(".", "").replace(",", ".")
    try:
        num = float(value)
    except ValueError:
        return None
    return num if num > 0 else None


def _date_tr(date: str) -> str:
    """YYYY-MM-DD -> DD.MM.YYYY (the form's date format)."""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", (date or "").strip())
    if not m:
        raise ValueError(f"bad date format (expected YYYY-MM-DD): {date!r}")
    y, mo, d = m.groups()
    return f"{d}.{mo}.{y}"


def parse_search_form(listing_html: str) -> dict:
    """Hidden inputs of the #hotelOtherValues form on a listing page."""
    m = re.search(
        r'<form[^>]*id="hotelOtherValues"[^>]*>(.*?)</form>', listing_html, re.S
    )
    if not m:
        raise ValueError("hotel search form not found on this Jolly listing page")
    form = dict(re.findall(r'name="([^"]+)"[^>]*value="([^"]*)"', m.group(1)))
    if not form.get("SearchParameters.Id"):
        raise ValueError("hotel search form has no destination id")
    return form


def build_search_post(
    form: dict,
    check_in: str = "",
    check_out: str = "",
    page: int = 1,
    hotel_name: str = "",
) -> dict:
    """Assemble the POST body for /hotel/GetListPagePartials, mirroring the
    site's own listOptionChange() call."""
    data = dict(form)
    if check_in:
        data["SearchParameters.StartDate"] = _date_tr(check_in)
    if check_out:
        data["SearchParameters.EndDate"] = _date_tr(check_out)
    default_filter = form.get("SearchParameters.DefaultFilterValue", "")
    data["filters"] = f"Location:{default_filter}" if default_filter else ""
    data["order"] = ""
    data["pageNo"] = str(max(page, 1))
    data["wordSort"] = ""
    data["rooms"] = "1"
    data["rawData"] = "true"
    if hotel_name and len(hotel_name) > 3:
        data["hotelName"] = hotel_name
    return data


def _parse_card(card: str) -> dict:
    def attr(name: str) -> str | None:
        m = re.search(rf'{name}="([^"]*)"', card)
        return html.unescape(m.group(1)) if m else None

    name_m = re.search(r'<h3 class="title">([^<]+)</h3>', card)
    loc_m = re.search(
        r'class="tour-route-map show-map"[^>]*>(.*?)<em', card, re.S
    )
    point_m = re.search(r'product-point">\s*([\d,]+)\s*<', card)
    count_m = re.search(r"\((\d+)\s*Değerlendirme\)", card)
    text_m = re.search(r'product-rating-text">\s*([^<]+?)\s*<', card)
    concept_m = re.search(r'hotel-campaign">\s*(?:<i[^>]*></i>)?\s*([^<]+?)\s*<', card, re.S)
    campaigns = sorted(
        set(_clean(c) for c in re.findall(r'campaign-text[^>]*>(.*?)</span>', card, re.S))
    )
    campaigns = [c for c in campaigns if c and len(c) < 200]
    url = attr("data-url")
    if url:
        url = url.split("?")[0]  # dated searches append ?Rooms=..&StartDate=..
    return {
        "name": _clean(name_m.group(1)) if name_m else None,
        "url": (BASE + url) if url else None,
        "slug": url.strip("/") if url else None,
        "location": _clean(loc_m.group(1)) if loc_m else None,
        "rating": float(point_m.group(1).replace(",", ".")) if point_m else None,
        "rating_count": int(count_m.group(1)) if count_m else None,
        "rating_text": _clean(text_m.group(1)) if text_m else None,
        "concept": _clean(concept_m.group(1)) if concept_m else None,
        "campaigns": campaigns,
        "total_price_tl": _price_tr(attr("data-totalprice")),
        "discounted_price_tl": _price_tr(attr("data-discountedprice")),
        "currency": attr("data-currency") or "TL",
    }


def parse_search_result(payload: dict, check_in: str = "", check_out: str = "") -> dict:
    """Parse a GetListPagePartials JSON response."""
    result_html = payload.get("hotelSearchResult") or ""
    cards = re.split(r'<div class="list" data-masterhotelid="', result_html)[1:]
    hotels = [_parse_card(c) for c in cards]
    hotels = [h for h in hotels if h.get("name")]
    return {
        "result_count": payload.get("resultCount"),
        "check_in": check_in or None,
        "check_out": check_out or None,
        "prices_available": bool(check_in and check_out),
        "count": len(hotels),
        "hotels": hotels,
    }


def parse_hotel_detail(html_text: str, url: str) -> dict:
    """Parse a hotel detail page."""
    name_m = re.search(r"<h1[^>]*>(.*?)</h1>", html_text, re.S)
    desc_m = re.search(r'name="description" content="([^"]+)"', html_text)
    # "Genel Bilgiler" section: first paragraph is the hotel description.
    info = ""
    i = html_text.find("Genel Bilgiler")
    if i != -1:
        seg = re.sub(r"<[^>]+>", " ", html_text[i : i + 4000])
        info = _clean(seg)
        info = info.replace("Genel Bilgiler", "", 1).strip()
        # cut at the "Otel Özellikleri" heading if present
        j = info.find("Otel Özellikleri")
        if j != -1:
            info = info[:j].strip()
    loc = re.search(r'addressLocality":"([^"]+)"', html_text)
    region = re.search(r'addressRegion":"([^"]+)"', html_text)
    concept = None
    for c in CONCEPTS:
        if c in (info or ""):
            concept = c
            break
    return {
        "name": _clean(name_m.group(1)) if name_m else None,
        "url": url,
        "location": loc.group(1) if loc else None,
        "region": region.group(1) if region else None,
        "concept": concept,
        "description": (desc_m.group(1).strip() if desc_m else ""),
        "about": info[:2000],
    }


def parse_campaigns(html_text: str) -> list[dict]:
    """Parse /kampanyalar: campaign links (deduped) with their image-alt titles."""
    out: dict[str, dict] = {}
    for m in re.finditer(
        r'<a[^>]+href="(/[^"]*(?:kampanya|kampanyasi)[^"]*)"[^>]*>(.*?)</a>',
        html_text,
        re.S | re.I,
    ):
        href, inner = m.group(1), m.group(2)
        alt_m = re.search(r'alt="([^"]+)"', inner)
        title = _clean(alt_m.group(1)) if alt_m else _clean(inner)
        if href not in out:
            out[href] = {"title": title or href.strip("/"), "url": BASE + href}
    # also catch campaign links whose anchor wraps no image (plain text)
    for m in re.finditer(
        r'href="(/[^"]*(?:kampanya|kampanyasi)[^"]*)"[^>]*>([^<]{5,120})<',
        html_text,
        re.I,
    ):
        href, text = m.group(1), _clean(m.group(2))
        if href not in out and text:
            out[href] = {"title": text, "url": BASE + href}
    return list(out.values())
