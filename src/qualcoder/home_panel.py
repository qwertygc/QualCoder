"""Home panel shown at the top of the Action Log tab on startup.

A modern, card-based landing surface that surfaces the most common actions
(new/open project, recent projects, help) and a snapshot of the current
project. It is built from ordinary Qt widgets so it stays consistent with the
theme palette and qtawesome icon set already used across QualCoder.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from PyQt6 import QtCore, QtGui, QtWidgets
import qtawesome as qta


class _CardButton(QtWidgets.QFrame):
    """A single clickable card with an icon, a title and an optional subtitle."""

    clicked = QtCore.pyqtSignal()

    def __init__(self, icon_name: str, title: str, subtitle: str = "",
                 accent: str = "#f89407", dark: bool = False,
                 parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._accent = accent
        self._dark = dark
        self.setObjectName("home_card")
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        self._icon_label = QtWidgets.QLabel()
        self._icon_label.setPixmap(
            qta.icon(icon_name, color=accent).pixmap(QtCore.QSize(28, 28)))
        layout.addWidget(self._icon_label)

        self._title_label = QtWidgets.QLabel(title)
        title_font = self._title_label.font()
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 1)
        self._title_label.setFont(title_font)
        layout.addWidget(self._title_label)

        self._subtitle_label = QtWidgets.QLabel(subtitle)
        self._subtitle_label.setWordWrap(True)
        self._subtitle_label.setObjectName("home_card_subtitle")
        layout.addWidget(self._subtitle_label)
        layout.addStretch(1)

        self._apply_style(False)

    def _apply_style(self, hovered: bool) -> None:
        border = self._accent if hovered else ("#3a3a3a" if self._dark else "#d0d0d0")
        hover_bg = "#3a3a3a" if self._dark else "#fafafa"
        sub_color = "#909090" if self._dark else "#707070"
        self.setStyleSheet(
            f"#home_card {{border: 1px solid {border}; border-radius: 10px;"
            f" background-color: {hover_bg if hovered else 'transparent'};}}"
            f" #home_card_subtitle {{color: {sub_color};}}")

    def enterEvent(self, event):  # noqa: N802 (Qt naming)
        self._apply_style(True)
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802 (Qt naming)
        self._apply_style(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event):  # noqa: N802 (Qt naming)
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class HomePanel(QtWidgets.QWidget):
    """Startup landing panel: quick actions, recent projects and status snapshot."""

    def __init__(self, app, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.app = app
        accent = self.app.highlight_color()

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 12)
        outer.setSpacing(14)

        title = QtWidgets.QLabel("QualCoder")
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 8)
        title_font.setBold(True)
        title.setFont(title_font)
        outer.addWidget(title)

        subtitle = QtWidgets.QLabel("Qualitative data analysis")
        sub_font = subtitle.font()
        sub_font.setPointSize(sub_font.pointSize() - 1)
        subtitle.setFont(sub_font)
        subtitle.setObjectName("home_subtitle")
        outer.addWidget(subtitle)

        # Quick action cards.
        self._cards_row = QtWidgets.QHBoxLayout()
        self._cards_row.setSpacing(12)
        outer.addLayout(self._cards_row)

        # Recent projects section.
        self._recent_label = QtWidgets.QLabel()
        rec_font = self._recent_label.font()
        rec_font.setBold(True)
        self._recent_label.setFont(rec_font)
        outer.addWidget(self._recent_label)

        self._recent_list = QtWidgets.QListWidget()
        self._recent_list.setObjectName("home_recent")
        self._recent_list.setMaximumHeight(120)
        self._recent_list.itemDoubleClicked.connect(self._open_recent)
        outer.addWidget(self._recent_list)

        outer.addStretch(1)
        self._refresh_recent()

    def set_action(self, icon_name: str, title: str, subtitle: str,
                   callback: Callable[[], None]) -> None:
        """Append a quick-action card wired to the given callback."""

        card = _CardButton(icon_name, title, subtitle, accent=self.app.highlight_color())
        card.clicked.connect(callback)
        self._cards_row.addWidget(card)

    def add_spacer(self) -> None:
        self._cards_row.addStretch(1)

    def refresh(self) -> None:
        """Re-render dynamic content (recent projects, project status)."""

        self._refresh_recent()

    def _refresh_recent(self) -> None:
        self._recent_list.clear()
        try:
            recents = self.app.read_previous_project_paths()
        except Exception:
            recents = []
        if recents:
            self._recent_label.setText("Recent projects")
        else:
            self._recent_label.setText("No recent projects")
        for entry in recents[:8]:
            display = entry.split("|")[-1] if "|" in entry else entry
            item = QtWidgets.QListWidgetItem(display)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, entry)
            self._recent_list.addItem(item)

    def _open_recent(self, item: QtWidgets.QListWidgetItem) -> None:
        entry = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if not entry:
            return
        path = entry.split("|")[0] if "|" in entry else entry
        window = self.window()
        if hasattr(window, "open_project"):
            window.open_project(path)
