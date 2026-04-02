"""
Проверки без ручного тестирования UI: компиляция, импорт сервера, опционально HTTP к локальному API.
Запуск из корня репозитория: python scripts/verify_project.py
"""
from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(root)

    print("1) compileall client + server …")
    r = subprocess.run(
        [sys.executable, "-m", "compileall", "client", "server", "-q"],
        cwd=root,
    )
    if r.returncode != 0:
        print("FAILED: compileall")
        return 1
    print("   OK")

    print("2) import FastAPI app + TestClient reports …")
    srv = os.path.join(root, "server")
    sys.path.insert(0, srv)
    try:
        from main import app
        from starlette.testclient import TestClient

        # Важно: lifespan (startup/shutdown) выполняется через контекстный менеджер.
        with TestClient(app) as tc:
            for path in (
                "/api/reports/lifecycle-by-stage",
                "/api/reports/site-export",
            ):
                r = tc.get(path)
                assert r.status_code == 200, f"{path} -> {r.status_code}"
            r = tc.get(
                "/api/laureates/laureate-awards/by-bulletin",
                params={"bulletin_number": "verify-test"},
            )
            assert r.status_code == 200, f"laureate-awards/by-bulletin -> {r.status_code}"
            assert isinstance(r.json(), list), "laureate-awards/by-bulletin must return a list"
    except Exception as e:
        print(f"FAILED: {e}")
        return 1
    print("   OK")

    print("3) optional: GET /api/health …")
    base = os.environ.get("VERIFY_API_BASE", "http://127.0.0.1:8000")
    try:
        import urllib.request

        with urllib.request.urlopen(f"{base}/api/health", timeout=3) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        if "ok" in body.lower():
            print(f"   OK ({base})")
        else:
            print(f"   unexpected body: {body[:200]}")
    except Exception as e:
        print(f"   SKIP (запустите сервер для проверки): {e}")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
