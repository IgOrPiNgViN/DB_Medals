"""
Создание страниц Qt в отдельном процессе (изоляция от сбоев pytest на Windows).
Запуск (опционально):
  set RUN_GUI_TESTS=1
  python -m pytest client/tests/test_ui_widgets_subprocess.py -q

На Windows нужен плагин «windows», не «offscreen» (его в PyQt5 обычно нет).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

CLIENT_ROOT = Path(__file__).resolve().parents[1]
PAGES = [
    ("bulletins", "ui.voting.bulletin", "BulletinPage"),
    ("vote_results", "ui.voting.vote_counting", "VoteCountingPage"),
    ("committee_list", "ui.committee.committee_list", "CommitteeListPage"),
    ("award_cards", "ui.awards.awards_cards", "AwardsCardsPage"),
]

_RUN_GUI = os.environ.get("RUN_GUI_TESTS", "").strip() in ("1", "true", "yes")

# Вставляется в дочерний процесс до QApplication (как в client/main.py).
_QT_BOOTSTRAP = '''
import os
import sys
from pathlib import Path

def _ensure_qt_plugins():
    try:
        import PyQt5
        base = Path(PyQt5.__file__).resolve().parent
        for rel in ("Qt5/plugins", "Qt/plugins"):
            plugins = base / rel.replace("/", os.sep)
            if plugins.is_dir():
                os.environ.setdefault("QT_PLUGIN_PATH", str(plugins))
                platforms = plugins / "platforms"
                if platforms.is_dir():
                    os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", str(platforms))
                break
    except Exception:
        pass

_ensure_qt_plugins()
if sys.platform == "win32":
    os.environ.pop("QT_QPA_PLATFORM", None)
elif os.environ.get("QT_QPA_PLATFORM") == "offscreen":
  pass
elif "QT_QPA_PLATFORM" not in os.environ:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
'''


def _subprocess_env() -> dict:
    env = {**os.environ}
    if sys.platform == "win32":
        env.pop("QT_QPA_PLATFORM", None)
    return env


def _spawn_page(module_path: str, class_name: str) -> subprocess.CompletedProcess:
    code = (
        _QT_BOOTSTRAP
        + f"""
import sys
sys.path.insert(0, {str(CLIENT_ROOT)!r})
from unittest.mock import MagicMock
from PyQt5.QtWidgets import QApplication
app = QApplication([])
api = MagicMock()
api.get_bulletins.return_value = []
api.get_awards.return_value = []
api.get_laureates.return_value = []
api.get_committee_members.return_value = []
api.get_protocols.return_value = []
api.get_bulletin_monitoring.return_value = []
api.get_vote_results.return_value = []
api.report_awards_laureates.return_value = []
api.get_bulletin_full.return_value = {{'sections': []}}
mod = __import__({module_path!r}, fromlist=[{class_name!r}])
cls = getattr(mod, {class_name!r})
w = cls(api)
if hasattr(w, 'refresh_data'):
    w.refresh_data()
elif hasattr(w, 'load_data'):
    w.load_data()
print('OK')
"""
    )
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(CLIENT_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
        env=_subprocess_env(),
    )


@pytest.mark.skipif(not _RUN_GUI, reason="GUI subprocess tests: set RUN_GUI_TESTS=1")
@pytest.mark.parametrize("page_key,module_path,class_name", PAGES)
def test_page_in_subprocess(page_key: str, module_path: str, class_name: str):
    r = _spawn_page(module_path, class_name)
    assert r.returncode == 0, (
        f"{page_key} failed:\nstdout={r.stdout}\nstderr={r.stderr}"
    )
    assert "OK" in r.stdout
