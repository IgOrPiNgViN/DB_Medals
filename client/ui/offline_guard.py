"""Помощники UX при потере связи."""

from __future__ import annotations

from PyQt5.QtWidgets import QMessageBox, QPushButton, QWidget

from api_client import APIError
from ui.connection_state import OFFLINE_WRITE_MESSAGE, connection_state
from ui.draft_store import draft_message_saved, save_draft


def is_connection_error(error: APIError | Exception) -> bool:
    if isinstance(error, APIError):
        return error.status_code == 0
    return False


def user_facing_error(error: APIError | Exception) -> str:
    if isinstance(error, APIError):
        if error.status_code == 0:
            detail = (error.detail or "").strip()
            if detail.startswith("Connection error"):
                return (
                    "Не удалось связаться с сервером.\n"
                    "Проверьте, что сервер запущен, и дождитесь «Подключено к серверу»."
                )
            if OFFLINE_WRITE_MESSAGE.split("\n")[0] in detail or "Нет связи" in detail:
                return OFFLINE_WRITE_MESSAGE
            return detail or str(error)
        return error.detail or str(error)
    return str(error)


def warn_if_offline(parent: QWidget | None, action: str = "Сохранение") -> bool:
    """True — можно продолжать; False — офлайн, показано предупреждение."""
    if connection_state.is_online:
        return True
    QMessageBox.warning(
        parent,
        "Нет связи с сервером",
        f"{action} недоступно.\n\n{OFFLINE_WRITE_MESSAGE}",
    )
    return False


def connect_write_buttons(*buttons: QPushButton) -> None:
    """Отключать кнопки изменения данных, пока нет связи с сервером."""

    def _sync(online: bool) -> None:
        for btn in buttons:
            btn.setEnabled(online)

    connection_state.changed.connect(_sync)
    _sync(connection_state.is_online)


def save_local_draft_on_failure(
    *,
    kind: str,
    entity_id: int,
    label: str,
    payload: dict,
    parent: QWidget | None,
    silent: bool,
    error: APIError,
) -> bool:
    """При ошибке связи сохранить черновик. True — черновик записан."""
    if not is_connection_error(error):
        return False
    key = f"{kind}_{entity_id}"
    save_draft(key, kind=kind, entity_id=entity_id, label=label, payload=payload)
    if not silent:
        QMessageBox.warning(
            parent,
            "Черновик сохранён",
            draft_message_saved(label),
        )
    return True
