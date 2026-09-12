"""Unit tests for the theme QSS loader.

These tests deliberately avoid importing PyQt so they run in any environment.
"""

import re
from pathlib import Path
from unittest import TestCase

from qualcoder.themes import PALETTES, _substitute, load_qss, native_tooltip_qss

_THEMES_DIR = Path(__file__).resolve().parent.parent / "src" / "qualcoder" / "themes"


class TestThemes(TestCase):

    def test_palettes_define_every_light_placeholder(self):
        qss = (_THEMES_DIR / "light.qss").read_text(encoding="utf-8")
        rendered = _substitute(qss, PALETTES["light"], 12, 12)
        self._assert_no_placeholders(rendered)

    def test_palettes_define_every_dark_placeholder(self):
        qss = (_THEMES_DIR / "dark.qss").read_text(encoding="utf-8")
        rendered = _substitute(qss, PALETTES["dark"], 12, 12)
        self._assert_no_placeholders(rendered)

    def test_load_qss_substitutes_font_sizes(self):
        qss = load_qss("light", 14, 10)
        self.assertIn("font-size: 14px", qss)
        self.assertIn("QTreeWidget {font-size: 10px", qss)
        self._assert_no_placeholders(qss)

    def test_load_qss_renders_dark(self):
        qss = load_qss("dark", 12, 12)
        self._assert_no_placeholders(qss)
        self.assertIn("#2a2a2a", qss)

    def test_unknown_palette_keys_do_not_leak(self):
        qss = "* {color: {{missing}};}"
        rendered = _substitute(qss, {}, 12, 12)
        self.assertIn("{{missing}}", rendered)

    def test_native_tooltip_qss_returns_snippet(self):
        snippet = native_tooltip_qss()
        self.assertIn("QToolTip", snippet)

    @staticmethod
    def _assert_no_placeholders(rendered: str) -> None:
        no_comments = re.sub(r"/\*.*?\*/", "", rendered, flags=re.DOTALL)
        leftovers = re.findall(r"\{\{[^}]+\}\}", no_comments)
        assert not leftovers, f"Unresolved placeholders: {leftovers}"
