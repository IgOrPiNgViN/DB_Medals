# -*- mode: python ; coding: utf-8 -*-
# Сборка: pyinstaller client/oon-pkr.spec  (из корня репозитория)
import os
import sys
from pathlib import Path

block_cipher = None

client_root = Path(os.path.dirname(os.path.abspath(SPEC)))
project_root = client_root.parent

# Qt-плагины (platforms) — явно, если hook PyInstaller не находит путь
_qt_binaries = []
try:
    import PyQt5

    _qt_base = Path(PyQt5.__file__).resolve().parent
    _plugins = _qt_base / "Qt5" / "plugins"
    if _plugins.is_dir():
        for sub in ("platforms", "styles", "imageformats"):
            d = _plugins / sub
            if d.is_dir():
                for f in d.glob("*"):
                    if f.is_file():
                        _qt_binaries.append((str(f), f"PyQt5/Qt5/plugins/{sub}"))
except Exception:
    pass

a = Analysis(
    [str(client_root / "launcher.py")],
    pathex=[str(client_root)],
    binaries=_qt_binaries,
    datas=[(str(client_root / "resources" / "styles.qss"), "resources")],
    hiddenimports=[
        "ui.main_window",
        "ui.awards.awards_cards",
        "ui.awards.award_detail",
        "ui.awards.lifecycle",
        "ui.awards.warehouse",
        "ui.awards.current_awards_report",
        "ui.laureates.laureate_cards",
        "ui.laureates.laureate_detail",
        "ui.laureates.laureate_lc",
        "ui.laureates.awards_laureates",
        "ui.laureates.incomplete_lc",
        "ui.laureates.lc_stages_report",
        "ui.laureates.statistics",
        "ui.committee.committee_list",
        "ui.committee.member_card",
        "ui.voting.bulletin",
        "ui.voting.monitoring",
        "ui.voting.vote_counting",
        "ui.voting.protocol",
        "ui.voting.extract",
        "ui.voting.ppz_submission",
        "ui.service.access_tables_page",
        "ui.service.db_export",
        "ui.print_helpers",
        "ui.numeric_sort_item",
        "ui.tab_helpers",
        "api_client",
        "config",
        "main",
        "httpx",
        "httpx._transports",
        "httpx._transports.default",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="OON-PKR-Awards",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulator=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="OON-PKR-Awards",
)
