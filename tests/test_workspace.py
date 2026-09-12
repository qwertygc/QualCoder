"""Unit tests for the dockable workspace helpers.

These tests cover the pure-Python indexing/ranking helpers in
``qualcoder.workspace``. They deliberately avoid importing PyQt so they run
in any environment.
"""

from unittest import TestCase

from qualcoder.workspace import index_codes, index_files, rank_entries


class _FakeApp:
    def get_code_names(self):
        return [{"name": "Anxiety", "cid": 1}, {"name": "Hope", "cid": 2}]

    def get_filenames(self):
        return [{"name": "interview1.txt", "id": 1}, {"name": "notes.md", "id": 2}]


class TestWorkspaceIndexing(TestCase):

    def setUp(self):
        self.app = _FakeApp()

    def test_index_codes_and_files(self):
        codes = index_codes(self.app)
        files = index_files(self.app)
        self.assertEqual(len(codes), 2)
        self.assertEqual(len(files), 2)
        self.assertEqual(codes[0]["kind"], "code")
        self.assertEqual(files[0]["kind"], "file")
        self.assertIn("key", codes[0])

    def test_index_handles_missing_project(self):
        class ClosedApp:
            def get_code_names(self):
                raise RuntimeError("no project")

            def get_filenames(self):
                raise RuntimeError("no project")

        self.assertEqual(index_codes(ClosedApp()), [])
        self.assertEqual(index_files(ClosedApp()), [])

    def test_rank_prefix_beats_substring(self):
        entries = index_codes(self.app) + index_files(self.app)
        ranked = rank_entries("an", entries)
        self.assertEqual(ranked[0]["title"], "Anxiety")

    def test_rank_empty_query_returns_all(self):
        entries = index_codes(self.app)
        self.assertEqual(len(rank_entries("", entries)), len(entries))

    def test_rank_no_match_returns_empty(self):
        entries = index_codes(self.app)
        self.assertEqual(rank_entries("zzzzz", entries), [])

    def test_rank_title_fallback(self):
        entries = index_files(self.app)
        ranked = rank_entries("notes", entries)
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0]["title"], "notes.md")
