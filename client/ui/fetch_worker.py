"""Фоновые HTTP-запросы без блокировки UI."""

from __future__ import annotations

from collections import deque
from typing import Callable, TypeVar

from PyQt5.QtCore import QThread, QTimer, QObject, pyqtSignal

T = TypeVar("T")

_MAX_CONCURRENT = 6
_active: list[QThread] = []
_pending: deque = deque()


class FetchActivity(QObject):
    """Сигнал об активных фоновых запросах (для индикатора в status bar)."""

    changed = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self._count = 0

    def set_count(self, count: int) -> None:
        if count == self._count:
            return
        self._count = count
        self.changed.emit(count)


activity = FetchActivity()


class _FetchWorker(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, fetch_fn: Callable[[], T]):
        super().__init__()
        self._fetch_fn = fetch_fn

    def run(self):
        try:
            self.succeeded.emit(self._fetch_fn())
        except Exception as exc:
            self.failed.emit(str(exc))


def thread_api_call(fn: Callable) -> T:
    from api_client import APIClient

    client = APIClient()
    try:
        return fn(client)
    finally:
        client.close()


def pending_count() -> int:
    return len(_active) + len(_pending)


def _notify() -> None:
    activity.set_count(pending_count())


def _pump() -> None:
    while len(_active) < _MAX_CONCURRENT and _pending:
        fetch_fn, ok, err = _pending.popleft()
        worker = _FetchWorker(fetch_fn)

        def _done(w=worker):
            if w in _active:
                _active.remove(w)
            _notify()
            QTimer.singleShot(0, _pump)

        worker.succeeded.connect(lambda r: QTimer.singleShot(0, lambda: ok(r)))
        worker.failed.connect(lambda e: QTimer.singleShot(0, lambda: err(e)))
        worker.finished.connect(_done)
        worker.finished.connect(worker.deleteLater)
        _active.append(worker)
        worker.start()
    _notify()


def run_api_fetch(
    fetch_fn: Callable[[], T],
    on_success: Callable[[T], None],
    on_error: Callable[[str], None],
) -> None:
    job = (fetch_fn, on_success, on_error)
    if len(_active) >= _MAX_CONCURRENT:
        _pending.append(job)
        _notify()
        return

    fetch_fn, on_success, on_error = job
    worker = _FetchWorker(fetch_fn)

    def _done(w=worker):
        if w in _active:
            _active.remove(w)
        _notify()
        QTimer.singleShot(0, _pump)

    # Колбэки — только в GUI-потоке (иначе индикатор «Подключено» не сбрасывается).
    worker.succeeded.connect(lambda r: QTimer.singleShot(0, lambda: on_success(r)))
    worker.failed.connect(lambda e: QTimer.singleShot(0, lambda: on_error(e)))
    worker.finished.connect(_done)
    worker.finished.connect(worker.deleteLater)
    _active.append(worker)
    _notify()
    worker.start()
