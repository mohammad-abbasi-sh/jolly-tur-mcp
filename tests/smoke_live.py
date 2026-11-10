"""Daily live smoke: one polite probe of the source site.

Exits 0 only when the site answers HTTP 200. Run by
.github/workflows/smoke.yml; also runnable locally:
    python tests/smoke_live.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jolly_mcp import http as _http

if __name__ == "__main__":
    result = _http.health_check()
    print(result)
    sys.exit(0 if result.get("status") == "ok" else 1)
