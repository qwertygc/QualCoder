"""Dockable workspace helpers: status bar and the locator bar.

This module implements the "QGIS-style" additions to the main window:

- ``StatusBarManager`` shows contextual information (project name and path,
  the currently open file/code, the number of coded segments) in the native
  ``QMainWindow`` status bar that QualCoder already has but does not use.

- ``LocatorBar`` is a command palette (a single search field plus a popup
  list) reachable from the status bar. It indexes menu actions, codes and
  files, so the user can find a code, open a file or trigger any menu entry
  by typing a few characters. It is the single highest "modern feel" payoff
  for the least architectural change.

Both helpers are self-contained and only need a reference to the
``MainWindow`` (``main``) and its ``App`` (``main.app``). They deliberately
avoid importing ``__main__`` so they can be unit-checked without PyQt where
the indexing helpers are extracted below.
"""

from __future__ import annotations

from typing import Iterable, List, Tuple


def _iter_menu_actions(menubar) -> Iterable:
    """Yield every leaf QAction reachable from the menu bar, with its path."""

    def walk(menu, prefix):
        for action in menu.actions():
            sub = action.menu()
            if sub is not None:
                yield from walk(sub, prefix + [action.text()])
                continue
            if action.text() and not action.isSeparator():
                yield action, prefix

    for top in menubar.actions():
        menu = top.menu()
        if menu is not None:
            yield from walk(menu, [top.text()])


def index_actions(menubar) -> List[dict]:
    """Build the action index used by the locator. Pure data, no PyQt calls."""

    entries: List[dict] = []
    for action, path in _iter_menu_actions(menubar):
        label = " > ".join(p for p in path if p) + " > " + action.text()
        entries.append({
            "kind": "action",
            "title": action.text(),
            "subtitle": " > ".join(p for p in path if p),
            "key": label.lower(),
            "data": action,
        })
    return entries


def index_codes(app) -> List[dict]:
    """Index project codes. Returns [] when no project is open."""

    try:
        codes = app.get_code_names()
    except Exception:
        return []
    entries: List[dict] = []
    for code in codes:
        entries.append({
            "kind": "code",
            "title": code["name"],
            "subtitle": "Code",
            "key": code["name"].lower(),
            "data": code,
        })
    return entries


def index_files(app) -> List[dict]:
    """Index project files (documents). Returns [] when no project is open."""

    try:
        files = app.get_filenames()
    except Exception:
        return []
    entries: List[dict] = []
    for f in files:
        entries.append({
            "kind": "file",
            "title": f["name"],
            "subtitle": "File",
            "key": f["name"].lower(),
            "data": f,
        })
    return entries


def rank_entries(query: str, entries: List[dict]) -> List[dict]:
    """Return ``entries`` whose key matches ``query``, best matches first.

    Substring matches rank above prefix matches, prefix above any. Pure data.
    """

    q = query.strip().lower()
    if not q:
        return entries
    substring: List[Tuple[int, dict]] = []
    prefix: List[Tuple[int, dict]] = []
    other: List[Tuple[int, dict]] = []
    for entry in entries:
        key = entry["key"]
        pos = key.find(q)
        if pos == 0:
            prefix.append((len(key), entry))
        elif pos > 0:
            substring.append((pos, entry))
        else:
            if q in entry["title"].lower():
                other.append((len(entry["title"]), entry))
    prefix.sort(key=lambda t: t[0])
    substring.sort(key=lambda t: t[0])
    other.sort(key=lambda t: t[0])
    return [e for _, e in prefix + substring + other]


try:  # The UI parts need PyQt6; keep import lazy so pure helpers stay testable.
    from PyQt6 import QtCore, QtGui, QtWidgets


    class CodesDock(QtWidgets.QDockWidget):
        """A persistent, always-visible project code browser dock.

        It mirrors the project's code/category tree so the user always has an
        overview of the coding framework while working in any dialog. It is a
        read/refresh browser (rename, delete, colour edits remain in the coding
        dialogs) and doubles as the selection target for the locator.
        """

        code_activated = QtCore.pyqtSignal(dict)

        def __init__(self, main):
            super().__init__(main.tr("Codes"), main)
            self.main = main
            self.app = main.app
            self.setObjectName("codes_dock")
            self.setAllowedAreas(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea
                                 | QtCore.Qt.DockWidgetArea.RightDockWidgetArea
                                 | QtCore.Qt.DockWidgetArea.BottomDockWidgetArea)
            self.setFeatures(QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable
                             | QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable
                             | QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetClosable)
            container = QtWidgets.QWidget(self)
            layout = QtWidgets.QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            self.filter = QtWidgets.QLineEdit(container)
            self.filter.setPlaceholderText(main.tr("Filter codes…"))
            self.filter.textChanged.connect(self._on_filter)
            self.tree = QtWidgets.QTreeWidget(container)
            self.tree.setObjectName("codes_dock_tree")
            self.tree.setColumnCount(2)
            self.tree.setHeaderLabels([main.tr("Name"), main.tr("Id")])
            self.tree.setColumnHidden(1, True)
            self.tree.setUniformRowHeights(True)
            self.tree.itemActivated.connect(self._on_item_activated)
            layout.addWidget(self.filter)
            layout.addWidget(self.tree)
            self.setWidget(container)

        def refresh(self):
            """Rebuild the tree from the open project (no-op if closed)."""

            self.tree.clear()
            if not getattr(self.app, "conn", None):
                return
            try:
                codes, categories = self.app.get_codes_categories()
            except Exception:
                return
            node_index: dict = {}
            # Top-level categories (supercatid is None), then nested.
            pending = list(categories)
            placed = True
            while pending and placed:
                placed = False
                keep = []
                for c in pending:
                    parent = node_index.get(f"catid:{c['supercatid']}") \
                        if c['supercatid'] is not None else None
                    if c['supercatid'] is None or parent is not None:
                        item = QtWidgets.QTreeWidgetItem([c['name'], f"catid:{c['catid']}"])
                        item.setToolTip(0, c.get('memo', ''))
                        if parent is None:
                            self.tree.addTopLevelItem(item)
                        else:
                            parent.addChild(item)
                        node_index[f"catid:{c['catid']}"] = item
                        placed = True
                    else:
                        keep.append(c)
                pending = keep
            for c in pending:  # orphan categories -> top level
                item = QtWidgets.QTreeWidgetItem([c['name'], f"catid:{c['catid']}"])
                self.tree.addTopLevelItem(item)
                node_index[f"catid:{c['catid']}"] = item
            # Codes nested under category (catid:) or parent code (supercid:).
            # Top-level codes have neither catid nor supercid.
            remaining = list(codes)
            placed = True
            while remaining and placed:
                placed = False
                keep = []
                for code in remaining:
                    parent_key = (f"catid:{code['catid']}" if code.get('catid') is not None
                                 else (f"cid:{code['supercid']}" if code.get('supercid') is not None
                                       else None))
                    parent = node_index.get(parent_key) if parent_key else None
                    if parent_key is None or parent is not None:
                        item = QtWidgets.QTreeWidgetItem([code['name'], f"cid:{code['cid']}"])
                        item.setToolTip(0, code.get('memo', ''))
                        color = code.get('color')
                        if color:
                            item.setBackground(0, QtGui.QBrush(QtGui.QColor(color)))
                        item.setData(0, QtCore.Qt.ItemDataRole.UserRole, code)
                        if parent is None:
                            self.tree.addTopLevelItem(item)
                        else:
                            parent.addChild(item)
                        node_index[f"cid:{code['cid']}"] = item
                        placed = True
                    else:
                        keep.append(code)
                remaining = keep
            for code in remaining:  # orphan codes -> top level
                item = QtWidgets.QTreeWidgetItem([code['name'], f"cid:{code['cid']}"])
                item.setData(0, QtCore.Qt.ItemDataRole.UserRole, code)
                self.tree.addTopLevelItem(item)
            self.tree.expandAll()

        def _on_item_activated(self, item):
            code = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
            if isinstance(code, dict):
                self.code_activated.emit(code)

        def _on_filter(self, text: str):
            text = text.strip().lower()
            it = QtWidgets.QTreeWidgetItemIterator(self.tree)
            while it.value():
                item = it.value()
                matches = not text or text in item.text(0).lower()
                item.setHidden(not matches)
                it += 1


    class StatusBarManager:
        """Owns the main window status bar and the locator input inside it."""

        def __init__(self, main):
            self.main = main
            self.app = main.app
            self.status = main.statusBar()
            self.project_label = QtWidgets.QLabel(self.main)
            self.project_label.setObjectName("status_project")
            self.context_label = QtWidgets.QLabel(self.main)
            self.context_label.setObjectName("status_context")
            self.locator = LocatorBar(self.main)

            self.status.setSizeGripEnabled(True)
            self.status.addWidget(self.project_label, 2)
            self.status.addPermanentWidget(self.context_label, 4)
            self.status.addPermanentWidget(self.locator, 3)
            self.context_label.setText("")

        def refresh(self):
            """Update project name/path and current context labels."""

            if self.app.project_name and self.app.project_path:
                self.project_label.setText(
                    f"{self.app.project_name}  —  {self.app.project_path}")
            else:
                self.project_label.setText("")
            self.update_context()

        def set_context(self, text: str):
            self.context_label.setText(text)

        def update_context(self):
            if not getattr(self.app, "conn", None):
                self.set_context("")
                return
            try:
                cur = self.app.conn.cursor()
                cur.execute("select count() from code_text")
                coded = cur.fetchone()[0]
                cur.execute("select count() from code_name")
                codes = cur.fetchone()[0]
                cur.execute("select count() from source")
                files = cur.fetchone()[0]
                self.set_context(
                    self.main.tr("Files: {f}   Codes: {c}   Coded segments: {s}").format(
                        f=files, c=codes, s=coded))
            except Exception:
                self.set_context("")


    class LocatorBar(QtWidgets.QWidget):
        """A compact command-palette input living in the status bar.

        Typing filters a popup list (codes, files, menu actions); activating an
        entry opens/selects the corresponding object.
        """

        activated = QtCore.pyqtSignal(object)

        def __init__(self, main):
            super().__init__(main)
            self.main = main
            self.app = main.app
            layout = QtWidgets.QHBoxLayout(self)
            layout.setContentsMargins(4, 0, 0, 0)
            layout.setSpacing(4)
            self.icon_label = QtWidgets.QLabel(self)
            self.icon_label.setText("⌘")
            self.icon_label.setObjectName("locator_icon")
            self.edit = QtWidgets.QLineEdit(self)
            self.edit.setObjectName("locator_edit")
            self.edit.setPlaceholderText(main.tr("Search codes, files, actions…  (Ctrl+K)"))
            self.edit.textChanged.connect(self._on_text_changed)
            self.edit.returnPressed.connect(self._on_return)
            layout.addWidget(self.icon_label)
            layout.addWidget(self.edit)

            self.popup = QtWidgets.QListWidget(self.main)
            self.popup.setWindowFlags(QtCore.Qt.WindowType.Popup)
            self.popup.setItemDelegate(QtWidgets.QStyledItemDelegate(self.popup))
            self.popup.setUniformItemSizes(True)
            self.popup.hide()
            self.popup.itemActivated.connect(self._on_item_activated)
            self.popup.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
            self._entries: List[dict] = []

        def focus_locator(self):
            self.edit.setFocus()
            self.edit.selectAll()

        def rebuild_index(self):
            """Rebuild the index from the menu bar and the open project."""

            entries = index_actions(self.main.ui.menubar)
            entries += index_codes(self.app)
            entries += index_files(self.app)
            self._entries = entries
            self._update_popup(self.edit.text())

        def _on_text_changed(self, text: str):
            self._update_popup(text)

        def _update_popup(self, text: str):
            ranked = rank_entries(text, self._entries)[:20]
            self.popup.clear()
            if not ranked:
                self.popup.hide()
                return
            for entry in ranked:
                item = QtWidgets.QListWidgetItem(
                    f"{entry['title']}   ·   {entry['subtitle']}")
                item.setData(QtCore.Qt.ItemDataRole.UserRole, entry)
                self.popup.addItem(item)
            self.popup.setCurrentRow(0)
            self.popup.adjustSize()
            bottom = self.main.statusBar().geometry().topLeft()
            self.popup.move(self.main.mapToGlobal(self.edit.pos() - QtCore.QPoint(0, self.popup.height())))
            self.popup.show()

        def _on_return(self):
            item = self.popup.currentItem()
            if item is None and self.popup.count():
                item = self.popup.item(0)
            self._activate_item(item)

        def _on_item_activated(self, item):
            self._activate_item(item)

        def _activate_item(self, item):
            self.popup.hide()
            self.edit.clear()
            if item is None:
                return
            entry = item.data(QtCore.Qt.ItemDataRole.UserRole)
            if entry is None:
                return
            kind = entry["kind"]
            if kind == "action" and entry.get("data") is not None:
                entry["data"].trigger()
            else:
                self.activated.emit(entry)
except Exception:  # pragma: no cover - PyQt not importable in pure-Python tests
    pass
