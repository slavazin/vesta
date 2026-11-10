import json
import os
import tempfile
import unittest

import support
from kernel import tree
from kernel.tree import DiskTree, Overlay


class Flaky(DiskTree):
    """A disk tree whose writes fail after a set number, the journal's own write not counted."""

    def __init__(self, root, allowed):
        DiskTree.__init__(self, root)
        self.allowed = allowed

    def write(self, path, text):
        if path != tree.JOURNAL:
            if self.allowed == 0:
                raise OSError("the disk went away")
            self.allowed -= 1
        DiskTree.write(self, path, text)


class Case(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self.temp.name)
        self.disk = DiskTree(self.root)
        self.disk.write("vesta/a.md", "a one\n")
        self.disk.write("vesta/b.md", "b one\n")
        self.disk.write("vesta/sub/c.md", "c one\n")
        support.write(os.path.join(self.root, "src", "main.txt"), "outside\r\nvesta\r\n")

    def tearDown(self):
        self.temp.cleanup()

    def on_disk(self, path):
        full = os.path.join(self.root, *path.split("/"))
        if not os.path.isfile(full):
            return None
        with open(full, "rb") as handle:
            return handle.read().decode("utf-8")


class Disk(Case):
    def test_reads_crlf_as_lf_and_writes_lf(self):
        self.assertEqual(self.disk.read("src/main.txt"), "outside\nvesta\n")
        self.disk.write("vesta/d.md", "x\ny\n")
        with open(os.path.join(self.root, "vesta", "d.md"), "rb") as handle:
            self.assertEqual(handle.read(), b"x\ny\n")

    def test_lists_and_walks(self):
        self.assertEqual(self.disk.list("vesta"), ["a.md", "b.md", "sub"])
        self.assertEqual(self.disk.list("vesta/none"), [])
        self.assertEqual(self.disk.walk("vesta"), ["vesta/a.md", "vesta/b.md", "vesta/sub/c.md"])

    def test_writes_only_under_the_home_folder(self):
        for path in ("src/main.txt", "vesta", "vestal/a.md", "../x", "/etc/x", "vesta/../src/x"):
            with self.assertRaises(ValueError, msg=path):
                self.disk.write(path, "no")
        self.assertEqual(self.on_disk("src/main.txt"), "outside\r\nvesta\r\n")

    def test_deletes_only_under_the_state_folder(self):
        self.disk.write("vesta/.state/x.json", "{}")
        self.disk.remove("vesta/.state/x.json")
        self.assertFalse(self.disk.exists("vesta/.state/x.json"))
        with self.assertRaises(ValueError):
            self.disk.remove("vesta/a.md")
        with self.assertRaises(ValueError):
            self.disk.remove("src/main.txt")

    def test_append_and_no_temporary_file_left(self):
        self.disk.append("vesta/log.md", "one\n")
        self.disk.append("vesta/log.md", "two\n")
        self.assertEqual(self.disk.read("vesta/log.md"), "one\ntwo\n")
        self.assertEqual([name for name in self.disk.list("vesta") if ".tmp" in name], [])


class OverlayReads(Case):
    def test_a_read_sees_pending_writes_and_moves_and_the_disk_is_unchanged(self):
        over = Overlay(self.disk)
        over.write("vesta/a.md", "a two\n")
        over.write("vesta/new/e.md", "e\n")
        over.move("vesta/b.md", "vesta/archive/b.md")
        self.assertEqual(over.read("vesta/a.md"), "a two\n")
        self.assertEqual(over.read("vesta/archive/b.md"), "b one\n")
        self.assertFalse(over.is_file("vesta/b.md"))
        with self.assertRaises(FileNotFoundError):
            over.read("vesta/b.md")
        self.assertTrue(over.is_dir("vesta/new"))
        self.assertEqual(over.list("vesta"), ["a.md", "archive", "new", "sub"])
        self.assertEqual(over.walk("vesta"), ["vesta/a.md", "vesta/archive/b.md", "vesta/new/e.md", "vesta/sub/c.md"])
        self.assertEqual(over.read("vesta/sub/c.md"), "c one\n")
        self.assertEqual(over.changed(), ["vesta/a.md", "vesta/archive/b.md", "vesta/b.md", "vesta/new/e.md"])
        self.assertEqual(self.on_disk("vesta/a.md"), "a one\n")
        self.assertEqual(self.on_disk("vesta/b.md"), "b one\n")
        self.assertIsNone(self.on_disk("vesta/new/e.md"))
        self.assertIsNone(self.on_disk("vesta/archive/b.md"))

    def test_a_pending_file_can_move_again_and_a_moved_path_can_be_rewritten(self):
        over = Overlay(self.disk)
        over.write("vesta/p.md", "p\n")
        over.move("vesta/p.md", "vesta/q.md")
        self.assertEqual(over.changed(), ["vesta/q.md"])
        over.move("vesta/a.md", "vesta/z.md")
        over.write("vesta/a.md", "a again\n")
        self.assertEqual(over.read("vesta/a.md"), "a again\n")
        over.commit()
        self.assertEqual(self.on_disk("vesta/a.md"), "a again\n")
        self.assertEqual(self.on_disk("vesta/z.md"), "a one\n")

    def test_commit_puts_everything_on_disk_and_leaves_no_journal(self):
        over = Overlay(self.disk)
        over.write("vesta/a.md", "a two\n")
        over.move("vesta/b.md", "vesta/archive/b.md")
        paths = over.commit()
        self.assertEqual(paths, ["vesta/a.md", "vesta/archive/b.md", "vesta/b.md"])
        self.assertEqual(self.on_disk("vesta/a.md"), "a two\n")
        self.assertIsNone(self.on_disk("vesta/b.md"))
        self.assertEqual(self.on_disk("vesta/archive/b.md"), "b one\n")
        self.assertIsNone(self.on_disk(tree.JOURNAL))
        self.assertEqual(over.changed(), [])
        self.assertEqual(tree.recover(self.disk), [])


class Journal(Case):
    def test_a_commit_interrupted_after_its_second_write_is_rolled_back(self):
        flaky = Flaky(self.root, allowed=2)
        over = Overlay(flaky)
        over.write("vesta/a.md", "a two\n")
        over.write("vesta/b.md", "b two\n")
        over.write("vesta/new.md", "new\n")
        over.move("vesta/sub/c.md", "vesta/sub/d.md")
        with self.assertRaises(OSError):
            over.commit()
        self.assertEqual(self.on_disk("vesta/a.md"), "a two\n")
        self.assertEqual(self.on_disk("vesta/b.md"), "b two\n")
        self.assertIsNotNone(self.on_disk(tree.JOURNAL))
        saved = json.loads(self.on_disk(tree.JOURNAL))["paths"]
        self.assertEqual(saved["vesta/a.md"], "a one\n")
        self.assertIsNone(saved["vesta/new.md"])

        restored = tree.recover(DiskTree(self.root))
        self.assertEqual(restored, ["vesta/a.md", "vesta/b.md"])
        self.assertEqual(self.on_disk("vesta/a.md"), "a one\n")
        self.assertEqual(self.on_disk("vesta/b.md"), "b one\n")
        self.assertIsNone(self.on_disk("vesta/new.md"))
        self.assertEqual(self.on_disk("vesta/sub/c.md"), "c one\n")
        self.assertIsNone(self.on_disk("vesta/sub/d.md"))
        self.assertIsNone(self.on_disk(tree.JOURNAL))

    def test_an_interruption_after_every_write_removes_what_the_commit_created(self):
        flaky = Flaky(self.root, allowed=3)
        over = Overlay(flaky)
        over.write("vesta/a.md", "a two\n")
        over.write("vesta/new.md", "new\n")
        over.move("vesta/b.md", "vesta/moved.md")
        over.write("vesta/z.md", "never written\n")
        with self.assertRaises(OSError):
            over.commit()
        self.assertEqual(self.on_disk("vesta/new.md"), "new\n")
        self.assertEqual(tree.recover(self.disk), ["vesta/a.md", "vesta/moved.md", "vesta/new.md"])
        self.assertEqual(self.on_disk("vesta/a.md"), "a one\n")
        self.assertEqual(self.on_disk("vesta/b.md"), "b one\n")
        self.assertIsNone(self.on_disk("vesta/new.md"))
        self.assertIsNone(self.on_disk("vesta/moved.md"))


class Guards(Case):
    def test_an_overlay_refuses_a_path_outside_the_home_folder_when_it_is_given(self):
        over = Overlay(self.disk)
        for path in ("src/main.txt", "zzz/out.txt", "../x", "vesta"):
            with self.assertRaises(ValueError, msg=path):
                over.write(path, "no")
        with self.assertRaises(ValueError):
            over.move("vesta/a.md", "src/a.md")
        with self.assertRaises(ValueError):
            over.write("vesta/a.md/child.md", "under a file")
        with self.assertRaises(ValueError):
            over.write("vesta/sub", "on a folder")
        with self.assertRaises(UnicodeEncodeError):
            over.write("vesta/s.md", "\ud800")
        self.assertEqual(over.changed(), [])

    def test_a_move_does_not_write_over_a_file(self):
        over = Overlay(self.disk)
        with self.assertRaises(ValueError):
            over.move("vesta/a.md", "vesta/b.md")
        with self.assertRaises(ValueError):
            self.disk.move("vesta/a.md", "vesta/b.md")
        self.assertEqual(self.on_disk("vesta/b.md"), "b one\n")
        self.disk.move("vesta/a.md", "vesta/moved/a.md")
        self.assertEqual(self.on_disk("vesta/moved/a.md"), "a one\n")
        self.assertIsNone(self.on_disk("vesta/a.md"))

    @unittest.skipIf(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0), "needs a folder that refuses writes")
    def test_a_move_that_fails_keeps_its_source(self):
        locked = os.path.join(self.root, "vesta", "locked")
        os.makedirs(locked)
        os.chmod(locked, 0o500)
        try:
            with self.assertRaises(OSError):
                self.disk.move("vesta/a.md", "vesta/locked/a.md")
        finally:
            os.chmod(locked, 0o700)
        self.assertEqual(self.on_disk("vesta/a.md"), "a one\n")

    def test_a_link_that_leads_out_of_the_home_folder_is_not_written_through(self):
        try:
            os.symlink(os.path.join(self.root, "src"), os.path.join(self.root, "vesta", "link"))
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest("links cannot be made here")
        with self.assertRaises(ValueError):
            self.disk.write("vesta/link/main.txt", "no")
        self.assertEqual(self.on_disk("src/main.txt"), "outside\r\nvesta\r\n")

    def test_a_write_puts_lf_on_disk_and_leaves_no_temporary_file(self):
        self.disk.write("vesta/crlf.md", "a\r\nb\n")
        self.assertEqual(self.on_disk("vesta/crlf.md"), "a\nb\n")
        with self.assertRaises(UnicodeEncodeError):
            self.disk.write("vesta/s.md", "\ud800")
        self.assertEqual(sorted(os.listdir(os.path.join(self.root, "vesta"))), ["a.md", "b.md", "crlf.md", "sub"])

    def test_the_overlay_removes_only_working_state(self):
        self.disk.write("vesta/.state/x.json", "{}")
        over = Overlay(self.disk)
        over.remove("vesta/.state/x.json")
        self.assertFalse(over.is_file("vesta/.state/x.json"))
        with self.assertRaises(ValueError):
            over.remove("vesta/a.md")
        over.commit()
        self.assertIsNone(self.on_disk("vesta/.state/x.json"))


class Recovery(Case):
    def test_a_temporary_file_left_by_a_killed_write_is_hidden_and_swept(self):
        self.disk.write(tree.JOURNAL, json.dumps({"paths": {"vesta/b.md": "b one\n"}}))
        support.write(os.path.join(self.root, "vesta", "b.md.tmp-4242"), "half")
        self.assertEqual(self.disk.list("vesta"), [".state", "a.md", "b.md", "sub"])
        self.assertEqual(tree.recover(self.disk), [])
        self.assertFalse(os.path.exists(os.path.join(self.root, "vesta", "b.md.tmp-4242")))

    def test_a_journal_that_does_not_read_is_reported_in_plain_words(self):
        from kernel.errors import UsageError
        for text in ("", "{not json", "[]"):
            self.disk.write(tree.JOURNAL, text)
            with self.assertRaises(UsageError) as caught:
                tree.recover(self.disk)
            self.assertIn("vesta/.state/journal.json does not read", str(caught.exception))

    def test_a_path_that_cannot_be_put_back_is_named_and_the_journal_kept(self):
        from kernel.errors import UsageError
        self.disk.write(tree.JOURNAL, json.dumps({"paths": {"src/main.txt": "old\n", "vesta/a.md": "a zero\n"}}))
        with self.assertRaises(UsageError) as caught:
            tree.recover(self.disk)
        self.assertIn("src/main.txt", str(caught.exception))
        self.assertEqual(self.on_disk("vesta/a.md"), "a zero\n")
        self.assertEqual(self.on_disk("src/main.txt"), "outside\r\nvesta\r\n")
        self.assertIsNotNone(self.on_disk(tree.JOURNAL))


class Paths(unittest.TestCase):
    def test_clean(self):
        self.assertEqual(tree.clean("./vesta//a.md"), "vesta/a.md")
        self.assertEqual(tree.clean("vesta\\walks\\start.md"), "vesta/walks/start.md")
        self.assertEqual(tree.clean("reports/"), "reports")
        for path in ("../a", "a/../../b", "/abs", "C:/x"):
            with self.assertRaises(ValueError, msg=path):
                tree.clean(path)


if __name__ == "__main__":
    unittest.main()
