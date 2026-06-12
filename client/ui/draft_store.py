"""Локальные черновики при недоступности сервера."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from api_client import APIClient, APIError


def _draft_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME")
    if base:
        root = Path(base) / "OONPKR" / "drafts"
    else:
        root = Path(__file__).resolve().parent.parent / ".cache" / "drafts"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _draft_path(key: str) -> Path:
    safe = key.replace("/", "_").replace("\\", "_")
    return _draft_dir() / f"{safe}.json"


def save_draft(key: str, *, kind: str, entity_id: int, label: str, payload: dict) -> None:
    data = {
        "key": key,
        "kind": kind,
        "entity_id": entity_id,
        "label": label,
        "payload": payload,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }
    _draft_path(key).write_text(
        json.dumps(data, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def list_pending_drafts() -> list[dict]:
    items: list[dict] = []
    for path in sorted(_draft_dir().glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                items.append(data)
        except (OSError, json.JSONDecodeError, TypeError):
            continue
    return items


def remove_draft(key: str) -> None:
    try:
        _draft_path(key).unlink(missing_ok=True)
    except OSError:
        pass


def draft_message_saved(label: str) -> str:
    return (
        f"Не удалось отправить на сервер («{label}»).\n"
        "Черновик сохранён на этом компьютере и будет отправлен "
        "автоматически после восстановления связи."
    )


def flush_all(api: APIClient) -> tuple[int, list[str]]:
    """Отправить все черновики на сервер. Возвращает (успешно, ошибки)."""
    ok = 0
    errors: list[str] = []
    for meta in list_pending_drafts():
        key = meta.get("key") or ""
        kind = meta.get("kind")
        entity_id = meta.get("entity_id")
        payload = meta.get("payload") or {}
        label = meta.get("label") or key
        try:
            eid = int(entity_id)
        except (TypeError, ValueError):
            remove_draft(key)
            continue
        try:
            if kind == "laureate":
                api.update_laureate(eid, payload)
            elif kind == "award":
                api.update_award(eid, payload)
            else:
                errors.append(f"{label}: неизвестный тип черновика")
                continue
            remove_draft(key)
            ok += 1
        except APIError as exc:
            errors.append(f"{label}: {exc.detail}")
    return ok, errors
