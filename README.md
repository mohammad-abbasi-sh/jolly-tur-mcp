# jolly-tur-mcp 🇹🇷

mcp-name: io.github.mohammad-abbasi-sh/jolly-tur-mcp

Unofficial **read-only** MCP server for **Jolly Tur** (jollytur.com), one of Türkiye's top-3 tour operators — hotel search with live prices, hotel detail and current campaigns.

> Part of the "Turkey MCP factory". Not affiliated with Jolly Tur.

## For AI agents

Add to your MCP client config (stdio):

```json
{
  "mcpServers": {
    "jolly": {
      "command": "uvx",
      "args": ["jolly-tur-mcp==0.1.0"]
    }
  }
}
```

Or run locally: `python -m jolly_mcp.server` (needs `mcp<2`, `curl-cffi`).

## Tools

| Tool | Description |
|------|-------------|
| `jolly_search_hotels` | Search hotels in a city — `city` slug ("antalya", "istanbul", "bodrum"…), `check_in`/`check_out` (YYYY-MM-DD, both needed for prices), `page`, `hotel_name` |
| `jolly_get_hotel` | Detail for one hotel — `hotel_slug` (e.g. "the-x-belek") or full URL |
| `jolly_list_campaigns` | Current campaigns from /kampanyalar (title + link) |

Example output (`jolly_search_hotels` / Antalya, 2026-11-20 → 2026-11-22):

```json
{"result_count": 1067, "count": 20,
 "hotels": [{"name": "The X Belek", "location": "Antalya, Serik, Belek, Kadriye",
 "rating": 9.6, "rating_count": 4186, "rating_text": "Mükemmel",
 "concept": "Ultra Her Şey Dahil",
 "total_price_tl": 21576.0, "discounted_price_tl": 13377.12}]}
```

Notes:
- Prices are Turkish Lira (TRY) for the requested stay; without dates the cards show no price (`prices_available: false`).
- Searches are slow (~10–15s: the site renders results server-side per query, and the endpoint occasionally stalls — the server retries once). Prefer one search per question.
- Data: Jolly's own listing/search flow (listing page + `GetListPagePartials` POST) — no key, no login, read-only.

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install "mcp<2" curl-cffi pytest
.venv/bin/python -m pytest tests/ -q
```

- `tests/test_hotels.py` — offline, parses real captured pages
- `tests/test_live.py` — 4 cautious live requests against jollytur.com

## License

MIT

---

Built by [Mohammad Abbasi](https://github.com/mohammad-abbasi-sh) — [Almanibama](https://almanibama.ir) · [mabbasi.ir](https://mabbasi.ir)
