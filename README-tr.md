# jolly-tur-mcp 🇹🇷

Türkiye'nin en büyük 3 tur operatöründen biri **Jolly Tur** (jollytur.com) için gayriresmî, **salt-okunur** MCP sunucusu — canlı fiyatlı otel arama, otel detayı ve güncel kampanyalar.

> "Türkiye MCP fabrikası" parçasıdır. Jolly Tur ile bağlantısı yoktur.

## Yapay zekâ ajanları için

MCP istemcinize ekleyin (stdio):

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

## Araçlar

| Araç | Açıklama |
|------|----------|
| `jolly_search_hotels` | Şehirde otel arama — `city` ("antalya", "istanbul", "bodrum"…), `check_in`/`check_out` (YYYY-MM-DD, fiyat için ikisi de gerekli), `page`, `hotel_name` |
| `jolly_get_hotel` | Tek otelin detayı — `hotel_slug` ("the-x-belek") veya tam URL |
| `jolly_list_campaigns` | Güncel kampanyalar (/kampanyalar) |

Notlar:
- Fiyatlar Türk Lirası (TRY), istenen konaklama içindir; tarihsiz aramada fiyat gösterilmez (`prices_available: false`).
- Aramalar yavaştır (~10–15 sn: site sonuçları sorgu başına sunucuda üretir; uç nokta bazen takılır — sunucu bir kez yeniden dener). Soru başına bir arama tercih edin.
- Veri: Jolly'nin kendi listeleme/arama akışı — anahtar yok, giriş yok, salt-okunur.

## Kurallar

Gayriresmî ve salt-okunur — giriş yok, API anahtarı yok, yazma yok. Testler: çevrimdışı fixture + canlı testler (13/13 yeşil).
