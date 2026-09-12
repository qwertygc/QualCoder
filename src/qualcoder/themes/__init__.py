"""Theme (QSS) support for QualCoder.

Stylesheets are kept as ``.qss`` files in this package and rendered with simple
``{{variable}}`` placeholder substitution so a single source of truth defines the
colour palette, spacing and typography for each theme.

The module deliberately avoids importing PyQt so that it can be imported and
unit-tested without a running Qt application.
"""

from __future__ import annotations

import platform
from pathlib import Path
from typing import Dict

_THEMES_DIR = Path(__file__).resolve().parent

# Canonical colour palette per theme.  These values are substituted into the
# corresponding ``.qss`` files before being handed to QApplication.setStyleSheet().
PALETTES: Dict[str, Dict[str, str]] = {
    "light": {
        "accent": "#f89407",
        "accent_hover": "#e08400",
        "accent_text": "#000000",
        "bg": "#efefef",
        "bg_window": "#efefef",
        "bg_input": "#fafafa",
        "bg_alternate": "#f9f9f9",
        "bg_text": "#fcfcfc",
        "card_bg": "#ffffff",
        "border": "#c4c4c4",
        "border_subtle": "#dcdcdc",
        "text": "#000000",
        "text_disabled": "#707070",
        "selection": "#000000",
        "selection_bg": "#ffffff",
        "splitter": "#d0d0d0",
        "scrollbar": "#cfcfcf",
        "scrollbar_hover": "#b0b0b0",
        "tooltip_bg": "#fffacd",
        "tooltip_border": "#f89407",
        "header_bg": "#f9f9f9",
        "button_bg": "#f9f9f9",
        "button_hover": "#f89407",
        "menu_selected": "#fafafa",
    },
    "dark": {
        "accent": "#f89407",
        "accent_hover": "#ffaa00",
        "accent_text": "#000000",
        "bg": "#2a2a2a",
        "bg_window": "#2a2a2a",
        "bg_input": "#2a2a2a",
        "bg_alternate": "#484848",
        "bg_text": "#2a2a2a",
        "card_bg": "#323232",
        "border": "#707070",
        "border_subtle": "#3a3a3a",
        "text": "#eeeeee",
        "text_disabled": "#707070",
        "selection": "#000000",
        "selection_bg": "#ffffff",
        "splitter": "#3a3a3a",
        "scrollbar": "#484848",
        "scrollbar_hover": "#5e5e5e",
        "tooltip_bg": "#2a2a2a",
        "tooltip_border": "#f89407",
        "header_bg": "#505050",
        "header_text": "#ffce42",
        "button_bg": "#858585",
        "button_hover": "#ffaa00",
        "menu_selected": "#3498db",
    },
}


def _substitute(qss: str, palette: Dict[str, str], font_size: int,
                tree_font_size: int) -> str:
    """Replace ``{{name}}`` placeholders with palette and font values."""

    values = dict(palette)
    values["font_size"] = str(font_size)
    values["tree_font_size"] = str(tree_font_size)
    for key, value in values.items():
        qss = qss.replace("{{" + key + "}}", value)
    return qss


def load_qss(name: str, font_size: int, tree_font_size: int) -> str:
    """Load and render the ``name`` stylesheet (``light`` or ``dark``)."""

    path = _THEMES_DIR / f"{name}.qss"
    qss = path.read_text(encoding="utf-8")
    return _substitute(qss, PALETTES[name], font_size, tree_font_size)


def native_tooltip_qss() -> str:
    """Return a small QSS snippet for tooltips under the native theme.

    The snippet adapts to the system colour scheme when available.
    """

    if platform.system() == "Darwin":
        return (
            "\nQToolTip {background-color: #2b2b2b; color: #ffffff;"
            " border: 1px solid #5f5f5f;}"
        )
    return (
        "\nQToolTip {background-color: #f7f7f7; color: #000000;"
        " border: 1px solid #bdbdbd;}"
    )
