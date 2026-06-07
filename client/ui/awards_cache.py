"""Кэш раздела «Награды»: списки + эскизы изображений (память + диск)."""

from __future__ import annotations

import json
import os
from pathlib import Path

_AWARD_TYPE_RU = {
    "medal": "Медали",
    "ppz": "ППЗ",
    "distinction": "Знаки отличия",
    "decoration": "Украшения",
}

_FILES = {
    "awards_all": "awards_all.json",
    "award_lifecycle": "award_lifecycle.json",
    "warehouse": "warehouse.json",
}


def _cache_root() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME")
    if base:
        root = Path(base) / "OONPKR" / "cache"
    else:
        root = Path(__file__).resolve().parent.parent / ".cache"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _images_dir() -> Path:
    d = _cache_root() / "award_images"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _image_path(award_id: int, side: str) -> Path:
    return _images_dir() / f"{award_id}_{side}.bin"


class AwardsCache:
    awards_all: list[dict] | None = None
    award_lifecycle: list | None = None
    warehouse: list | None = None
    preload_pending: set[str] = set()
    preload_done: set[str] = set()
    _image_bytes: dict[tuple[int, str], bytes] = {}
    _thumb_pixmaps: dict[int, object] = {}

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
        cls._warm_images_from_disk()

    @classmethod
    def _warm_images_from_disk(cls) -> None:
        """Загрузить сохранённые эскизы в память (быстрый показ каталога)."""
        img_dir = _images_dir()
        if not img_dir.is_dir():
            return
        for path in img_dir.glob("*.bin"):
            name = path.stem
            if "_" not in name:
                continue
            try:
                award_id_str, side = name.rsplit("_", 1)
                award_id = int(award_id_str)
            except ValueError:
                continue
            if side not in ("front", "back"):
                continue
            try:
                data = path.read_bytes()
            except OSError:
                continue
            if data:
                cls._image_bytes[(award_id, side)] = data
                if award_id not in cls._thumb_pixmaps:
                    pm = cls._bytes_to_thumb(data)
                    if pm is not None:
                        cls._thumb_pixmaps[award_id] = pm

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
    def filter_awards(cls, award_type_ru: str | None) -> list[dict] | None:
        if cls.awards_all is None:
            return None
        if not award_type_ru:
            return list(cls.awards_all)
        return [
            a for a in cls.awards_all
            if _AWARD_TYPE_RU.get(a.get("award_type"), a.get("award_type")) == award_type_ru
        ]

    @classmethod
    def set_awards_all(cls, data: list | None) -> None:
        cls.awards_all = data
        cls._save("awards_all", data)

    @classmethod
    def set_award_lifecycle(cls, data: list | None) -> None:
        cls.award_lifecycle = data
        cls._save("award_lifecycle", data)

    @classmethod
    def set_warehouse(cls, data: list | None) -> None:
        cls.warehouse = data
        cls._save("warehouse", data)

    @classmethod
    def get_image_bytes(cls, award_id: int, side: str) -> bytes | None:
        key = (award_id, side)
        if key in cls._image_bytes:
            return cls._image_bytes[key]
        path = _image_path(award_id, side)
        if not path.is_file():
            return None
        try:
            data = path.read_bytes()
        except OSError:
            return None
        if data:
            cls._image_bytes[key] = data
        return data or None

    @classmethod
    def set_image_bytes(cls, award_id: int, side: str, data: bytes | None) -> None:
        if not data:
            return
        cls._image_bytes[(award_id, side)] = data
        pm = cls._bytes_to_thumb(data)
        if pm is not None:
            cls._thumb_pixmaps[award_id] = pm
        try:
            _image_path(award_id, side).write_bytes(data)
        except OSError:
            pass

    @classmethod
    def get_catalog_image_bytes(
        cls,
        award_id: int,
        has_front: bool,
        has_back: bool,
    ) -> bytes | None:
        if has_front:
            data = cls.get_image_bytes(award_id, "front")
            if data:
                return data
        if has_back:
            return cls.get_image_bytes(award_id, "back")
        return None

    @classmethod
    def get_thumb_pixmap(cls, award_id: int, has_front: bool, has_back: bool):
        from PyQt5.QtGui import QPixmap

        if award_id in cls._thumb_pixmaps:
            return cls._thumb_pixmaps[award_id]
        data = cls.get_catalog_image_bytes(award_id, has_front, has_back)
        if not data:
            return None
        pm = cls._bytes_to_thumb(data)
        if pm is not None:
            cls._thumb_pixmaps[award_id] = pm
        return pm

    @staticmethod
    def _bytes_to_thumb(data: bytes):
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QImage, QPixmap

        p = QPixmap()
        if p.loadFromData(data):
            return p.scaled(160, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        img = QImage.fromData(data)
        if img.isNull():
            return None
        return QPixmap.fromImage(img).scaled(
            160, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation,
        )

    @classmethod
    def invalidate_award_images(cls, award_id: int) -> None:
        cls._thumb_pixmaps.pop(award_id, None)
        for side in ("front", "back"):
            cls._image_bytes.pop((award_id, side), None)
            try:
                _image_path(award_id, side).unlink(missing_ok=True)
            except OSError:
                pass

    @classmethod
    def preload_missing_images(cls, awards: list | None = None) -> None:
        """Фоновая догрузка эскизов, которых ещё нет в кэше."""
        from ui.fetch_worker import run_api_fetch, thread_api_call

        items = awards or cls.awards_all or []
        for award in items:
            aid = int(award.get("id") or 0)
            if not aid:
                continue
            if award.get("has_image") and cls.get_image_bytes(aid, "front") is None:
                cls._fetch_image(aid, "front", run_api_fetch, thread_api_call)
            if award.get("has_image_back") and cls.get_image_bytes(aid, "back") is None:
                cls._fetch_image(aid, "back", run_api_fetch, thread_api_call)

    @staticmethod
    def _fetch_image(award_id: int, side: str, run_api_fetch, thread_api_call) -> None:
        def fetch():
            return thread_api_call(
                lambda api: api.get_award_image_bytes(award_id, side),
            )

        def on_ok(data):
            if data:
                AwardsCache.set_image_bytes(award_id, side, data)

        run_api_fetch(fetch, on_success=on_ok, on_error=lambda _e: None)
