"""Общий кэш прочих разделов (НК и т.д.)."""

from __future__ import annotations

import json
import os
from pathlib import Path


def _cache_root() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME")
    if base:
        root = Path(base) / "OONPKR" / "cache"
    else:
        root = Path(__file__).resolve().parent.parent / ".cache"
    root.mkdir(parents=True, exist_ok=True)
    return root


_FILES = {
    "committee_members": "committee_members.json",
}


class AppCache:
    committee_members: list | None = None
    preload_pending: set[str] = set()
    preload_done: set[str] = set()

    @classmethod
    def load_from_disk(cls) -> None:
        for attr, filename in _FILES.items():
            path = _cache_root() / filename
            if not path.is_file():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                setattr(cls, attr, data)
            except (OSError, json.JSONDecodeError, TypeError):
                pass

    @classmethod
    def _save(cls, attr: str, data) -> None:
        filename = _FILES.get(attr)
        if not filename or data is None:
            return
        try:
            (_cache_root() / filename).write_text(
                json.dumps(data, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        except OSError:
            pass

    @classmethod
    def mark_preload_start(cls, keys: set[str]) -> None:
        cls.preload_pending = set(keys)
        cls.preload_done.clear()

    @classmethod
    def mark_preload_done(cls, key: str) -> None:
        cls.preload_pending.discard(key)
        cls.preload_done.add(key)

    @classmethod
    def set_committee_members(cls, data: list | None) -> None:
        cls.committee_members = data
        cls._save("committee_members", data)
