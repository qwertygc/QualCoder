"""Item delegates for the codes tree.

ColorChipDelegate draws a small rounded colour swatch at the left of the Name
column (column 0). The swatch colour is taken from the item background role that
``CodeTreeController`` already sets via ``item.setBackground(0, color)``, so no
counting or storage logic changes.

CountBadgeDelegate renders the Count column (column 3) as a rounded badge
instead of plain text, so coding frequencies read like modern notification
chips. It is purely presentational: the count text is still set by the coding
hosts via ``QTreeWidgetItem.setText(3, ...)`` (e.g. ``"5"`` or ``"5 (12)"``),
so this delegate does not change any counting logic.
"""

from __future__ import annotations

from typing import Optional

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt


class ColorChipDelegate(QtWidgets.QStyledItemDelegate):
    """Draw a rounded colour swatch before the code name in the Name column.

    The colour is read from the item's background role (set by the tree
    controller with ``setBackground(0, code_color)``). When a row has no
    background colour (e.g. category rows) nothing extra is drawn and the
    default rendering is used, so categories keep their plain look.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

    @staticmethod
    def _chip_color(index: QtCore.QModelIndex):
        brush = index.data(QtCore.Qt.ItemDataRole.BackgroundRole)
        if isinstance(brush, QtGui.QBrush) and brush.style() != Qt.BrushStyle.NoBrush:
            color = brush.color()
            if color.isValid():
                return color
        return None

    def paint(self, painter: QtGui.QPainter, option: QtWidgets.QStyleOptionViewItem,
              index: QtCore.QModelIndex) -> None:
        chip_color = self._chip_color(index)
        if chip_color is None:
            super().paint(painter, option, index)
            return

        chip_size = option.rect.height() - 8
        if chip_size < 6:
            chip_size = 6
        if chip_size > 18:
            chip_size = 18
        chip_x = option.rect.x() + 4
        chip_y = option.rect.y() + (option.rect.height() - chip_size) // 2
        chip_rect = QtCore.QRectF(chip_x, chip_y, chip_size, chip_size)

        # The code colour is shown as a chip, not as a full-row fill, so rows keep
        # the theme's clean selection/hover styling. Drop the background brush
        # before delegating to the base renderer for text + selection.
        shifted = QtWidgets.QStyleOptionViewItem(option)
        shifted.backgroundBrush = QtGui.QBrush(Qt.BrushStyle.NoBrush)
        shifted.rect = option.rect.adjusted(int(chip_size) + 10, 0, 0, 0)

        painter.save()
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        path = QtGui.QPainterPath()
        path.addRoundedRect(chip_rect, chip_size / 2.0, chip_size / 2.0)
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 40), 1))
        painter.fillPath(path, chip_color)
        painter.drawPath(path)
        painter.restore()

        super().paint(painter, shifted, index)

    def sizeHint(self, option: QtWidgets.QStyleOptionViewItem,
                 index: QtCore.QModelIndex) -> QtCore.QSize:
        size = super().sizeHint(option, index)
        if self._chip_color(index) is not None:
            return QtCore.QSize(size.width() + 24, size.height())
        return size


class CountBadgeDelegate(QtWidgets.QStyledItemDelegate):
    """Draw the Count column as a rounded accent badge."""

    def __init__(self, app, parent: Optional[QtCore.QObject] = None):
        super().__init__(parent)
        self._app = app

    def _palette_colors(self) -> tuple:
        """Return (badge_bg, badge_text, accent) adapted to the theme."""

        try:
            accent = QtGui.QColor(self._app.highlight_color())
        except Exception:
            accent = QtGui.QColor("#f89407")
        try:
            dark = self._app.is_dark_theme()
        except Exception:
            dark = False
        if dark:
            return QtGui.QColor("#3a3a3a"), QtGui.QColor("#eeeeee"), accent
        return QtGui.QColor("#eaeaea"), QtGui.QColor("#202020"), accent

    def paint(self, painter: QtGui.QPainter, option: QtWidgets.QStyleOptionViewItem,
              index: QtCore.QModelIndex) -> None:
        text = index.data(QtCore.Qt.ItemDataRole.DisplayRole)
        if text is None or str(text) == "":
            super().paint(painter, option, index)
            return
        text = str(text)

        painter.save()
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        bg, fg, accent = self._palette_colors()
        rect = option.rect.adjusted(6, 4, -6, -4)

        badge_path = QtGui.QPainterPath()
        radius = min(rect.height() / 2, 10)
        badge_path.addRoundedRect(QtCore.QRectF(rect), radius, radius)

        # Subtle accent-tinted background using the highlight color at low alpha.
        tint = QtGui.QColor(accent)
        tint.setAlpha(38)
        painter.fillPath(badge_path, tint)
        painter.setPen(QtGui.QPen(accent, 1))
        painter.drawPath(badge_path)

        painter.setPen(QtGui.QPen(fg, 1))
        font = painter.font()
        if font.pointSize() > 0:
            font.setPointSize(max(7, font.pointSize() - 1))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()

    def sizeHint(self, option: QtWidgets.QStyleOptionViewItem,
                 index: QtCore.QModelIndex) -> QtCore.QSize:
        size = super().sizeHint(option, index)
        return QtCore.QSize(size.width() + 12, size.height())
