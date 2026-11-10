import os
import tempfile
import unittest

import support
from kernel import glob, ids, root
from kernel.clock import Clock, FixedClock
from kernel.finding import ERROR, WARNING, Finding

GLOB_CASES = [
    ("scripts/release*", "scripts/release.sh", True),
    ("scripts/release*", "scripts/release/notes.md", False),
    ("scripts/release*", "scripts/prerelease.sh", False),
    ("*.md", "README.md", True),
    ("*.md", "docs/README.md", False),
    ("docs/*.md", "docs/a.md", True),
    ("docs/*.md", "docs/sub/a.md", False),
    ("docs/**/*.md", "docs/a.md", True),
    ("docs/**/*.md", "docs/sub/deep/a.md", True),
    ("docs/**", "docs/sub/deep/a.md", True),
    ("docs/**", "docs", True),
    ("docs/**", "documents/a.md", False),
    ("**/test_*.py", "test_a.py", True),
    ("**/test_*.py", "engine/tests/test_a.py", True),
    ("**/test_*.py", "engine/tests/a_test.py", False),
    ("src/?.py", "src/a.py", True),
    ("src/?.py", "src/ab.py", False),
    ("src/?.py", "src//.py", False),
    ("reports/2026-q?/notes.md", "reports/2026-q4/notes.md", True),
    ("a/**/b/**/c", "a/x/b/y/z/c", True),
    ("a/**/b/**/c", "a/b/c", True),
    ("a/**/b/**/c", "a/c", False),
    ("src/[ab].py", "src/a.py", False),
    ("src/[ab].py", "src/[ab].py", True),
    ("src/a+b.(py)", "src/a+b.(py)", True),
    ("letters/", "letters", True),
    ("./letters/*.txt", "letters/a.txt", True),
    ("Docs/*.md", "docs/a.md", False),
]


class Glob(unittest.TestCase):
    def test_the_case_table(self):
        self.assertGreaterEqual(len(GLOB_CASES), 20)
        for pattern, path, expected in GLOB_CASES:
            self.assertEqual(glob.match(pattern, path), expected, "%s against %s" % (pattern, path))


class Ids(unittest.TestCase):
    def test_an_internal_id_is_eight_hex_characters_and_avoids_taken_values(self):
        feed = [b"\x00" * 16, b"\x00" * 16, b"\x01" * 16]
        first = ids.new_uid("decisions", "2026-01-05T09:00:00Z", "A title", random=lambda n: b"\x00" * 16)
        self.assertRegex(first, r"^[0-9a-f]{8}$")
        second = ids.new_uid("decisions", "2026-01-05T09:00:00Z", "A title", taken=[first], random=lambda n: feed.pop(0))
        self.assertNotEqual(first, second)
        self.assertEqual(feed, [])
        self.assertNotEqual(ids.new_uid("a", "t", "x"), ids.new_uid("a", "t", "x"))

    def test_both_label_schemes(self):
        self.assertEqual(ids.numbered_label("D", 3, 4), "D-004")
        self.assertEqual(ids.numbered_label("D", 3, 1000), "D-1000")
        self.assertEqual(ids.numbered_label("REC", 4, 12), "REC-0012")
        self.assertEqual(ids.dated_label("O", "2026-03-14", "a3f29c0e"), "O-20260314-a3f29c0e")

    def test_numbers_and_the_next_free_one(self):
        self.assertEqual(ids.number_of("D-004", "D"), 4)
        self.assertIsNone(ids.number_of("P-004", "D"))
        self.assertIsNone(ids.number_of("README", "D"))
        self.assertEqual(ids.next_number(["D-001", "D-007", "P-020", "README"], "D"), 8)
        self.assertEqual(ids.next_number([], "D"), 1)

    def test_numbered_labels_sort_by_number(self):
        labels = ["D-1000", "D-999", "D-010", "D-9"]
        self.assertEqual(sorted(labels, key=ids.sort_key), ["D-9", "D-010", "D-999", "D-1000"])

    def test_references(self):
        self.assertEqual(ids.format_ref("D-003", "7f3a9c2e"), "D-003@7f3a9c2e")
        self.assertEqual(ids.parse_ref("D-003@7f3a9c2e"), ("D-003", "7f3a9c2e"))
        self.assertEqual(ids.parse_ref("D-003"), ("D-003", None))
        self.assertEqual(ids.parse_ref("7f3a9c2e"), (None, "7f3a9c2e"))
        self.assertEqual(ids.parse_ref("O-20260314-a3f29c0e@a3f29c0e"), ("O-20260314-a3f29c0e", "a3f29c0e"))

    def test_trigger_references_and_dated_labels(self):
        self.assertEqual(ids.trigger_ref("D-004", "t1"), "D-004/t1")
        self.assertEqual(ids.split_trigger_ref("D-004@7f3a9c2e/t2"), ("D-004@7f3a9c2e", "t2"))
        self.assertEqual(ids.split_trigger_ref("walks/close.md"), ("walks/close.md", None))
        self.assertIsNone(ids.number_of("O-20260314-12345678", "O"))
        dated = ["O-20260314-12345678", "O-20260314-0a345678"]
        self.assertEqual(sorted(dated, key=ids.sort_key), sorted(dated))


class Root(unittest.TestCase):
    def test_the_root_is_two_levels_above_an_installed_engine(self):
        with tempfile.TemporaryDirectory() as base:
            base = os.path.realpath(base)
            for name in (".engine", ".engine.next"):
                engine = os.path.join(base, "project", "vesta", name)
                os.makedirs(engine)
                self.assertEqual(root.from_engine(engine), os.path.join(base, "project"))
            for elsewhere in (os.path.join(base, "repo", "engine"), os.path.join(base, "vesta", "engine")):
                os.makedirs(elsewhere)
                self.assertIsNone(root.from_engine(elsewhere), elsewhere)

    def test_the_root_is_found_from_a_folder_inside_the_project(self):
        with tempfile.TemporaryDirectory() as base:
            base = os.path.realpath(base)
            support.write(os.path.join(base, "project", "vesta", "vesta.yml"), "schema: 1\n")
            deep = os.path.join(base, "project", "src", "deep")
            os.makedirs(deep)
            self.assertEqual(root.from_folder(deep), os.path.join(base, "project"))
            self.assertEqual(root.from_folder(os.path.join(base, "project")), os.path.join(base, "project"))
            self.assertIsNone(root.from_folder(base))


class FindingAndClock(unittest.TestCase):
    def test_a_finding_prints_in_the_one_form(self):
        finding = Finding(ERROR, "records", "vesta/decisions/D-001.md", 7, "the field `why` is empty")
        self.assertEqual(finding.render(), "error records vesta/decisions/D-001.md:7 the field `why` is empty")
        self.assertEqual(finding, Finding(ERROR, "records", "vesta/decisions/D-001.md", 7, "the field `why` is empty"))
        self.assertNotEqual(finding, Finding(WARNING, "records", "vesta/decisions/D-001.md", 7, "the field `why` is empty"))
        with self.assertRaises(ValueError):
            Finding("note", "records", "a", 1, "b")

    def test_clock_forms(self):
        clock = FixedClock("2026-03-14T09:12:00Z")
        self.assertEqual((clock.timestamp(), clock.today()), ("2026-03-14T09:12:00Z", "2026-03-14"))
        clock.advance(seconds=60, days=1)
        self.assertEqual(clock.timestamp(), "2026-03-15T09:13:00Z")
        self.assertRegex(Clock().timestamp(), r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertRegex(Clock().today(), r"^\d{4}-\d\d-\d\d$")


if __name__ == "__main__":
    unittest.main()
