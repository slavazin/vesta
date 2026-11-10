import contextlib
import io
import os
import tempfile
import unittest

import support
from support import glue

neutrality = support.tool("neutrality")
# A made-up list: the list a maintainer keeps is private and is not in the repository.
TERMS = os.path.join(support.DATA, "sample-terms.txt")

# Strings the regular-expression terms must catch, built at run time so this file holds none of them.
SAMPLES = [
    glue(chr(167), " ", "4"),
    glue(chr(167), "4"),
    glue("V", "2"),
    glue("[", "I", " ", "2", "]"),
    glue("[", "I", "12", "]"),
    glue("I", "7"),
]


def run(root):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = neutrality.main(["--root", root, "--terms", TERMS])
    return code, out.getvalue()


class Planted(unittest.TestCase):
    def setUp(self):
        self.terms = neutrality.read_terms(TERMS)
        self.assertTrue(self.terms)

    def test_each_plain_term_is_reported_with_file_line_and_term(self):
        for label, _ in self.terms:
            if label.startswith("re:"):
                continue
            with tempfile.TemporaryDirectory() as root:
                support.write(os.path.join(root, "notes", "a.md"), "first line\nbefore " + label.swapcase() + " after\n")
                code, out = run(root)
                self.assertEqual(code, 1, label)
                self.assertIn("notes/a.md:2: " + label, out)

    def test_a_plain_term_inside_a_longer_word_is_not_reported(self):
        for label, _ in self.terms:
            if label.startswith("re:"):
                continue
            with tempfile.TemporaryDirectory() as root:
                support.write(os.path.join(root, "a.md"), "x" + label + "x\n")
                self.assertEqual(run(root)[0], 0, label)

    def test_a_term_joined_by_an_underscore_a_hyphen_or_a_digit_is_reported(self):
        for label, _ in self.terms:
            if label.startswith("re:"):
                continue
            for text in (label + "_stats", "my-" + label, label + "2", "(" + label + ")"):
                with tempfile.TemporaryDirectory() as root:
                    support.write(os.path.join(root, "a.md"), text + "\n")
                    self.assertEqual(run(root)[0], 1, text)

    def test_the_words_of_a_term_may_be_parted_by_other_white_space_or_a_hyphen(self):
        several = [label for label, _ in self.terms if " " in label and not label.startswith("re:")]
        self.assertTrue(several)
        for label in several:
            for joiner in ("  ", "\t", "-", "_"):
                with tempfile.TemporaryDirectory() as root:
                    support.write(os.path.join(root, "a.md"), joiner.join(label.split()) + "\n")
                    self.assertEqual(run(root)[0], 1, repr(joiner))

    def test_a_term_in_a_file_or_folder_name_is_reported(self):
        term = next(label for label, _ in self.terms if not label.startswith("re:") and " " not in label)
        with tempfile.TemporaryDirectory() as root:
            support.write(os.path.join(root, term, "notes.md"), "clean\n")
            code, out = run(root)
            self.assertEqual(code, 1)
            self.assertIn("(in the path)", out)

    def test_a_file_that_is_not_text_is_itself_reported_and_litter_is_left_out(self):
        term = next(label for label, _ in self.terms if not label.startswith("re:"))
        with tempfile.TemporaryDirectory() as root:
            for litter in ("pkg/__pycache__/a.cpython-39.pyc", ".DS_Store"):
                os.makedirs(os.path.dirname(os.path.join(root, litter)) or root, exist_ok=True)
                with open(os.path.join(root, litter), "wb") as handle:
                    handle.write(b"\xff" + term.encode("utf-8"))
            self.assertEqual(run(root)[0], 0)
            support.write(os.path.join(root, "pkg", "__pycache__", "notes.md"), term + "\n")
            self.assertEqual(run(root)[0], 1)
            os.remove(os.path.join(root, "pkg", "__pycache__", "notes.md"))
            with open(os.path.join(root, "bad.md"), "wb") as handle:
                handle.write(b"\xff " + term.encode("utf-8"))
            code, out = run(root)
            self.assertEqual(code, 1)
            self.assertIn("bad.md:0: not UTF-8 text", out)

    def test_each_expression_term_is_reported(self):
        for label, pattern in self.terms:
            if not label.startswith("re:"):
                continue
            sample = next((s for s in SAMPLES if pattern.search(s)), None)
            self.assertIsNotNone(sample, "no sample here matches " + label)
            with tempfile.TemporaryDirectory() as root:
                support.write(os.path.join(root, "a.txt"), "see " + sample + " here\n")
                code, out = run(root)
                self.assertEqual(code, 1, label)
                self.assertIn("a.txt:1: " + label, out)

    def test_an_expression_term_is_case_sensitive(self):
        with tempfile.TemporaryDirectory() as root:
            support.write(os.path.join(root, "a.txt"), glue("v", "2") + " and " + glue("i", "7") + "\n")
            self.assertEqual(run(root)[0], 0)


class Exemptions(unittest.TestCase):
    def test_the_four_exemptions_and_nothing_else(self):
        term = next(label for label, _ in neutrality.read_terms(TERMS) if not label.startswith("re:"))
        line = term + "\n"
        with tempfile.TemporaryDirectory() as root:
            for exempt in ("spec/a.md", ".git/config", "LICENSE", "engine/tests/data/a.txt"):
                support.write(os.path.join(root, *exempt.split("/")), line)
            self.assertEqual(run(root)[0], 0)
            for scanned in ("engine/tests/a.py", "docs/LICENSE", "docs/spec/a.md", "specs.md"):
                path = os.path.join(root, *scanned.split("/"))
                support.write(path, line)
                code, out = run(root)
                self.assertEqual(code, 1, scanned)
                self.assertIn(scanned + ":1: ", out)
                os.remove(path)

    def test_the_output_states_its_residue(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertIn("residue:", run(root)[1])


class Repository(unittest.TestCase):
    def test_this_repository_passes_or_says_that_nothing_was_checked(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = neutrality.main([])
        self.assertEqual(code, 0, out.getvalue())
        if os.path.isfile(neutrality.default_terms(support.REPO)):
            self.assertIn(" 0 matches.", out.getvalue())
        else:
            self.assertIn("nothing was checked", out.getvalue())

    def test_no_list_is_said_and_a_named_list_that_is_missing_is_an_error(self):
        with tempfile.TemporaryDirectory() as root:
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                self.assertEqual(neutrality.main(["--root", root]), 0)
                self.assertEqual(neutrality.main(["--root", root, "--terms", os.path.join(root, "absent.txt")]), 2)
            self.assertIn("nothing was checked", out.getvalue())
            self.assertNotIn("0 matches", out.getvalue())
            self.assertIn("no terms file", err.getvalue())

    def test_the_private_list_is_kept_out_of_the_repository(self):
        ignored = support.read(os.path.join(support.REPO, ".gitignore")).split("\n")
        self.assertIn(os.path.relpath(neutrality.default_terms(support.REPO), support.REPO).replace(os.sep, "/"), ignored)


if __name__ == "__main__":
    unittest.main()
