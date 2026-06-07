"""Кэш данных раздела «Лауреаты» (память + диск между запусками)."""

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
    "laureates": "laureates.json",
    "awards_laureates": "awards_laureates.json",
    "incomplete_lifecycle": "incomplete_lifecycle.json",
    "lifecycle_by_stage": "lifecycle_by_stage.json",
    "statistics_all": "statistics_all.json",
}


class LaureatesCache:
    laureates: list[dict] | None = None
    awards_laureates: list | None = None
    awards_laureates_flat: list[dict] | None = None
    incomplete_lifecycle: list | None = None
    lifecycle_by_stage: dict | None = None
    statistics_all: list | None = None
    _disk_loaded: bool = False
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
        if cls.awards_laureates is not None:
            cls.awards_laureates_flat = cls.flatten_awards_laureates(cls.awards_laureates)
        cls._disk_loaded = True

    @classmethod
    def flatten_awards_laureates(cls, report_data: list | None) -> list[dict]:
        rows: list[dict] = []
        for award_group in report_data or []:
            award_name = award_group.get("award_name", "")
            award_type = award_group.get("award_type", "")
            for lau in award_group.get("laureates", []):
                rows.append({
                    "la_id": lau.get("laureate_award_id", ""),
                    "award_name": award_name,
                    "award_type": award_type,
                    "full_name": lau.get("full_name", ""),
                    "category": lau.get("category", ""),
                    "assigned_date": lau.get("assigned_date", ""),
                })
        return rows

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
    def set_laureates(cls, data: list[dict] | None) -> None:
        cls.laureates = data
        cls._save("laureates", data)

    @classmethod
    def filter_laureates(cls, category: str | None) -> list[dict] | None:
        if cls.laureates is None:
            return None
        if not category:
            return list(cls.laureates)
        return [l for l in cls.laureates if l.get("category") == category]

    @classmethod
    def set_awards_laureates(cls, data) -> None:
        cls.awards_laureates = data
        cls.awards_laureates_flat = cls.flatten_awards_laureates(data)
        cls._save("awards_laureates", data)

    @classmethod
    def mark_preload_start(cls, keys: set[str]) -> None:
        cls.preload_pending = set(keys)
        cls.preload_done.clear()

    @classmethod
    def mark_preload_done(cls, key: str) -> None:
        cls.preload_pending.discard(key)
        cls.preload_done.add(key)

    @classmethod
    def should_skip_background_fetch(cls, cache_key: str) -> bool:
        """Не дублировать HTTP, если preload ещё идёт или уже обновил кэш."""
        return cache_key in cls.preload_pending or cache_key in cls.preload_done

    @classmethod
    def set_incomplete_lifecycle(cls, data) -> None:
        cls.incomplete_lifecycle = data
        cls._save("incomplete_lifecycle", data)

    @classmethod
    def set_lifecycle_by_stage(cls, data: dict | None) -> None:
        cls.lifecycle_by_stage = data
        cls._save("lifecycle_by_stage", data)

    @classmethod
    def set_statistics_all(cls, data: list | None) -> None:
        cls.statistics_all = data
        cls._save("statistics_all", data)
