"""Unit tests for the coder comparison Kappa statistics, including subcorpus selection.

The tests build a minimal in-memory SQLite project (source, code_name, code_text)
and call DialogReportCoderComparisons.calculate_agreement_for_code directly,
bypassing the Qt widget setup. This verifies that Cohen's Kappa and the
agreement percentages are calculated over the selected subcorpus only.
"""

import os
import sqlite3
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qualcoder.reports import DialogReportCoderComparisons


class FakeApp:
    """Minimal App stand-in providing a sqlite connection and code/category lists."""

    def __init__(self, conn):
        self.conn = conn

    def get_codes_categories(self):
        return [], []


def build_project():
    """Two text files, one code, two coders with different overlaps per file.

    File 1 (length 10): coder A codes chars 0-4, coder B codes chars 0-4 (agree)
    File 2 (length 10): coder A codes chars 0-4, coder B codes chars 5-9 (disagree)
    """
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("CREATE TABLE source (id integer primary key, name text, fulltext text, "
                "memo text, owner text, date text)")
    cur.execute("INSERT INTO source (id, name, fulltext, memo, owner, date) VALUES "
                "(1, 'interview_one', 'aaaaaaaaaa', '', 'default', 'd')")
    cur.execute("INSERT INTO source (id, name, fulltext, memo, owner, date) VALUES "
                "(2, 'interview_two', 'bbbbbbbbbb', '', 'default', 'd')")
    cur.execute("CREATE TABLE code_name (cid integer primary key, name text, memo text, "
                "catid integer, owner text, date text, color text, supercid integer)")
    cur.execute("INSERT INTO code_name (cid, name, memo, catid, owner, date, color, supercid) "
                "VALUES (1, 'topic', '', NULL, 'default', 'd', '#F5A9A9', NULL)")
    cur.execute("CREATE TABLE code_text (ctid integer primary key, cid integer, fid integer, "
                "seltext text, pos0 integer, pos1 integer, owner text, date text, memo text, "
                "avid integer, important integer)")
    # File 1: full agreement on chars 0-4
    cur.execute("INSERT INTO code_text (ctid, cid, fid, seltext, pos0, pos1, owner, date, memo, avid, important) "
                "VALUES (1, 1, 1, 'aaaaa', 0, 5, 'coderA', 'd', '', NULL, NULL)")
    cur.execute("INSERT INTO code_text (ctid, cid, fid, seltext, pos0, pos1, owner, date, memo, avid, important) "
                "VALUES (2, 1, 1, 'aaaaa', 0, 5, 'coderB', 'd', '', NULL, NULL)")
    # File 2: complete disagreement, disjoint spans
    cur.execute("INSERT INTO code_text (ctid, cid, fid, seltext, pos0, pos1, owner, date, memo, avid, important) "
                "VALUES (3, 1, 2, 'bbbbb', 0, 5, 'coderA', 'd', '', NULL, NULL)")
    cur.execute("INSERT INTO code_text (ctid, cid, fid, seltext, pos0, pos1, owner, date, memo, avid, important) "
                "VALUES (4, 1, 2, 'bbbbb', 5, 10, 'coderB', 'd', '', NULL, NULL)")
    conn.commit()
    return conn


class TestCalculateAgreementForCode(unittest.TestCase):

    def setUp(self):
        self.conn = build_project()
        self.dialog = DialogReportCoderComparisons.__new__(DialogReportCoderComparisons)
        self.dialog.app = FakeApp(self.conn)
        self.dialog.selected_coders = ["coderA", "coderB"]
        self.dialog.selected_file_ids = None
        cur = self.conn.cursor()
        cur.execute("select id, name, length(fulltext) from source where fulltext is not null")
        rows = cur.fetchall()
        self.dialog.file_summaries = [(row[0], row[2]) for row in rows]
        self.dialog.file_names = {row[0]: row[1] for row in rows}
        self.dialog.codes = []
        self.dialog.categories = []

    def tearDown(self):
        self.conn.close()

    def test_all_files_default_is_full_corpus(self):
        total = self.dialog.calculate_agreement_for_code(1)
        self.assertEqual(total["characters"], 20)
        self.assertEqual(total["dual_coded"], 5)
        self.assertEqual(total["single_coded"], 10)
        self.assertEqual(total["uncoded"], 5)

    def test_subcorpus_selection_filters_files(self):
        self.dialog.selected_file_ids = [1]
        total = self.dialog.calculate_agreement_for_code(1)
        self.assertEqual(total["characters"], 10)
        self.assertEqual(total["dual_coded"], 5)
        self.assertEqual(total["single_coded"], 0)
        self.assertEqual(total["uncoded"], 5)
        self.assertEqual(total["agree_coded_only"], 100.0)

    def test_subcorpus_selection_changes_kappa(self):
        total_all = self.dialog.calculate_agreement_for_code(1)
        self.dialog.selected_file_ids = [1]
        total_sub = self.dialog.calculate_agreement_for_code(1)
        self.assertNotEqual(total_all["kappa"], total_sub["kappa"])

    def test_perfect_agreement_gives_kappa_one(self):
        self.dialog.selected_file_ids = [1]
        total = self.dialog.calculate_agreement_for_code(1)
        self.assertEqual(total["kappa"], 1.0)

    def test_selected_file_ids_may_contain_unknown_ids(self):
        self.dialog.selected_file_ids = [1, 99]
        total = self.dialog.calculate_agreement_for_code(1)
        self.assertEqual(total["characters"], 10)


if __name__ == "__main__":
    unittest.main()
