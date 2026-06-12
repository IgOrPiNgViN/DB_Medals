"""Глобальное состояние связи клиента с сервером."""

from __future__ import annotations

from PyQt5.QtCore import QObject, pyqtSignal


OFFLINE_WRITE_MESSAGE = (
    "Нет связи с сервером. Сохранение и другие изменения временно недоступны.\n\n"
    "• Дождитесь индикатора «Подключено к серверу» внизу окна\n"
    "• Или нажмите «Проверить связь» в жёлтой полосе сверху\n"
    "• Несохранённые данные можно хранить в локальном черновике"
)


class ConnectionState(QObject):
    """Единая точка правды: онлайн / офлайн."""

    changed = pyqtSignal(bool)

    def __init__(self) -> None:
        super().__init__()
        self._online = False
        self._ever_online = False

    @property
    def is_online(self) -> bool:
        return self._online

    @property
    def ever_online(self) -> bool:
        return self._ever_online

    def set_online(self, online: bool) -> None:
        if online:
            self._ever_online = True
        if self._online == online:
            return
        self._online = online
        self.changed.emit(online)

    def note_success(self) -> None:
        """Любой успешный HTTP-запрос — связь есть."""
        self.set_online(True)


connection_state = ConnectionState()
