#!/usr/bin/env python3
"""
Сборка десктоп-клиента в exe (PyInstaller).

Из корня репозитория:
  python scripts/build_client_exe.py

Сборка в %TEMP%\\oon-pkr-build (ASCII): venv + копия client + PyInstaller,
чтобы обойти ошибки путей с кириллицей в профиле пользователя.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    print("$", " ".join(str(c) for c in cmd))
    r = subprocess.run(cmd, cwd=str(cwd) if cwd else None)
    if r.returncode != 0:
        raise SystemExit(r.returncode)


def _install_dist(built: Path, target: Path) -> Path:
    """Copy PyInstaller output into repo dist/. Handles locked old builds on Windows."""
    if target.exists():
        last_err: OSError | None = None
        for attempt in range(5):
            try:
                shutil.rmtree(target)
                last_err = None
                break
            except PermissionError as err:
                last_err = err
                if attempt < 4:
                    print(
                        f"   Старая сборка занята (попытка {attempt + 1}/5). "
                        "Закройте OON-PKR-Awards.exe, если он запущен…",
                    )
                    time.sleep(2)
        if last_err is not None:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            target = target.parent / f"{target.name}-{stamp}"
            print()
            print(
                "Не удалось удалить прежнюю папку dist (файлы заблокированы).\n"
                "Закройте клиент и удалите старую папку вручную при необходимости.\n"
                f"Новая сборка скопирована сюда:\n  {target}",
            )

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(built, target)
    return target


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    client_src = root / "client"
    build_root = Path(tempfile.gettempdir()) / "oon-pkr-build"

    if build_root.exists():
        shutil.rmtree(build_root, ignore_errors=True)
    build_root.mkdir(parents=True)

    venv_dir = build_root / "venv"
    src_dir = build_root / "client"
    dist_dir = build_root / "dist"
    work_dir = build_root / "work"

    print("1) venv в", venv_dir)
    _run([sys.executable, "-m", "venv", str(venv_dir)])

    if sys.platform == "win32":
        py = venv_dir / "Scripts" / "python.exe"
    else:
        py = venv_dir / "bin" / "python"

    print("2) зависимости")
    _run([str(py), "-m", "pip", "install", "--upgrade", "pip", "-q"])
    _run(
        [
            str(py),
            "-m",
            "pip",
            "install",
            "-r",
            str(client_src / "requirements.txt"),
            "pyinstaller>=6.0",
            "-q",
        ],
    )

    print("3) копия client ->", src_dir)
    shutil.copytree(
        client_src,
        src_dir,
        ignore=shutil.ignore_patterns("tests", "__pycache__", "*.pyc"),
    )

    print("4) PyInstaller")
    spec = src_dir / "oon-pkr.spec"
    _run(
        [
            str(py),
            "-m",
            "PyInstaller",
            str(spec),
            "--noconfirm",
            "--distpath",
            str(dist_dir),
            "--workpath",
            str(work_dir),
        ],
        cwd=build_root,
    )

    built = dist_dir / "OON-PKR-Awards"
    if not built.is_dir():
        print("Ошибка: нет", built)
        return 1

    out = _install_dist(built, root / "dist" / "OON-PKR-Awards")

    env_example = root / ".env.example"
    if env_example.is_file():
        shutil.copy(env_example, out / ".env.example")

    (out / "ПРОЧТИ_МЕНЯ.txt").write_text(
        "ООН ПКР — клиент\n\n"
        "1. Скопируйте .env.example в .env\n"
        "2. В .env: SERVER_URL=http://<сервер>:<порт>  (без /api)\n"
        "3. Запустите OON-PKR-Awards.exe\n\n"
        "На сервере должен быть доступен API (Docker / uvicorn).\n",
        encoding="utf-8",
    )

    print()
    print("Готово. Папка для заказчика:")
    print(f"  {out}")
    print(f"  exe: {out / 'OON-PKR-Awards.exe'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
