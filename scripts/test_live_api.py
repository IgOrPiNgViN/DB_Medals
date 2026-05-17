#!/usr/bin/env python3
"""
Проверка запущенного API (бэкенд должен работать: uvicorn или docker).
Из корня: python scripts/test_live_api.py
Переменная SERVER_URL (по умолчанию http://localhost:8000).
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT = os.path.join(ROOT, "client")
if CLIENT not in sys.path:
    sys.path.insert(0, CLIENT)

from api_client import APIClient, APIError  # noqa: E402


def check(label: str, fn) -> bool:
    try:
        fn()
        print(f"  OK  {label}")
        return True
    except APIError as e:
        print(f"  FAIL {label}: {e}")
        return False
    except Exception as e:
        print(f"  FAIL {label}: {e}")
        return False


def main() -> int:
    base = os.environ.get("SERVER_URL", "http://localhost:8000")
    api = APIClient(base_url=f"{base}/api")
    ok = True

    print(f"Live API: {base}/api\n")

    ok &= check("health", lambda: api.health_check())
    ok &= check("awards list", lambda: api.get_awards())
    ok &= check("laureates list", lambda: api.get_laureates())
    ok &= check("committee list", lambda: api.get_committee_members())
    ok &= check("bulletins list", lambda: api.get_bulletins())
    ok &= check("protocols list", lambda: api.get_protocols())
    ok &= check("reports lifecycle-by-stage", lambda: api.report_lifecycle_by_stage())
    ok &= check("reports site-export", lambda: api.report_site_export())
    ok &= check("access mirror tables", lambda: api.list_access_mirror_tables())

    def create_bulletin_smoke():
        b = api.create_bulletin(
            {
                "number": "LIVE-SMOKE-1",
                "bulletin_type": "medal",
                "voting_start": "2026-06-01",
                "voting_end": "2026-06-30",
            },
        )
        api.delete_bulletin(b["id"])

    ok &= check("bulletin create/delete", create_bulletin_smoke)

    api.close()
    print()
    if ok:
        print("Live API smoke: all checks passed.")
        return 0
    print("Live API smoke: some checks failed (is the server running?).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
