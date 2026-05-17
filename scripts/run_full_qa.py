#!/usr/bin/env python3
"""
Полная QA-проверка: API (pytest server) + UI smoke (pytest client).
Запуск из корня: python scripts/run_full_qa.py
"""
from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(root)
    py = sys.executable

    steps = [
        ([py, "-m", "compileall", "client", "server", "-q"], "compileall"),
        (
            [py, "-m", "pytest", "server/tests", "-v", "--tb=short", "-q"],
            "server API tests (PostgreSQL, бэкенд не нужен)",
        ),
        (
            [py, "-m", "pytest", "client/tests/test_ui_imports.py", "-q", "--tb=short"],
            "client UI imports",
        ),
    ]
    if os.environ.get("RUN_GUI_TESTS", "").strip() in ("1", "true", "yes"):
        steps.append(
            (
                [py, "-m", "pytest", "client/tests/test_ui_widgets_subprocess.py", "-q"],
                "client GUI subprocess (optional)",
            ),
        )

    failed = False
    for cmd, label in steps:
        print(f"\n=== {label} ===")
        r = subprocess.run(cmd, cwd=root)
        if r.returncode != 0:
            print(f"FAILED: {label}")
            failed = True
        else:
            print(f"OK: {label}")

    if not failed:
        print("\n=== optional: verify_project (compile + TestClient) ===")
        subprocess.run([py, "scripts/verify_project.py"], cwd=root)
        print("\n=== optional: live API (нужен запущенный uvicorn/docker) ===")
        r = subprocess.run([py, "scripts/test_live_api.py"], cwd=root)
        if r.returncode != 0:
            print("(live API skipped or failed — запустите бэкенд для полной проверки)")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
