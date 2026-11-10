import os
import tempfile
import unittest

import support
from support import glue

build = support.tool("build")
FENCE = "`" * 4


class Blocks(unittest.TestCase):
    def test_four_backtick_markdown_blocks_are_taken_in_order(self):
        text = "\n".join([
            "intro", FENCE + "markdown", "# One", "```", "inner", "```", FENCE,
            "```markdown", "not this", "```",
            FENCE + "markdown", "# Two", FENCE, "",
        ])
        self.assertEqual(build.blocks(text), ["# One\n```\ninner\n```\n", "# Two\n"])

    def test_an_unclosed_block_is_an_error(self):
        with self.assertRaises(ValueError):
            build.blocks(FENCE + "markdown\n# One\n")


class Refresh(unittest.TestCase):
    def fixture(self, root, count=None):
        spec = os.path.join(root, build.SPEC)
        support.write(os.path.join(spec, build.TERMS), "term-a\r\nterm-b\r\n")
        parts = []
        for name, first in build.VERBATIM[:count]:
            parts += ["text about " + name, FENCE + "markdown", first, "body of " + name, FENCE]
        support.write(os.path.join(spec, build.TEMPLATES), "\n".join(parts) + "\n")

    def test_terms_and_blocks_land_in_the_test_data(self):
        with tempfile.TemporaryDirectory() as root:
            self.fixture(root)
            build.refresh_test_data(root)
            data = os.path.join(root, "engine", "tests", "data")
            self.assertEqual(support.read(os.path.join(data, build.TERMS)), "term-a\nterm-b\n")
            for name, first in build.VERBATIM:
                self.assertEqual(support.read(os.path.join(data, "verbatim", name)), first + "\nbody of " + name + "\n")

    def test_a_missing_block_is_an_error(self):
        with tempfile.TemporaryDirectory() as root:
            self.fixture(root, count=3)
            with self.assertRaises(ValueError):
                build.refresh_test_data(root)

    def test_without_the_specification_nothing_is_written(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(build.refresh_test_data(root), [])
            self.assertFalse(os.path.exists(os.path.join(root, "engine")))

    def test_the_engine_copy_leaves_out_tests_and_bytecode(self):
        with tempfile.TemporaryDirectory() as root:
            support.write(os.path.join(root, "engine", "kernel", "a.py"), "A = 1\n")
            support.write(os.path.join(root, "engine", "tests", "test_a.py"), "")
            support.write(os.path.join(root, "engine", "kernel", "__pycache__", "a.pyc"), "")
            support.write(os.path.join(root, "skills", "vesta-init", "engine", "stale.py"), "")
            target = build.copy_engine(root)
            self.assertTrue(os.path.isfile(os.path.join(target, "kernel", "a.py")))
            self.assertFalse(os.path.exists(os.path.join(target, "tests")))
            self.assertFalse(os.path.exists(os.path.join(target, "kernel", "__pycache__")))
            self.assertFalse(os.path.exists(os.path.join(target, "stale.py")))


class EngineCopy(unittest.TestCase):
    def listing(self, folder, skip=()):
        found = {}
        for here, names, leaves in os.walk(folder):
            names[:] = [name for name in names if name != "__pycache__" and os.path.join(here, name) not in skip]
            for leaf in leaves:
                if leaf.endswith(".pyc") or leaf == ".DS_Store":
                    continue
                path = os.path.join(here, leaf)
                found[os.path.relpath(path, folder).replace(os.sep, "/")] = support.read(path)
        return found

    def test_the_copy_in_the_init_skill_equals_the_engine(self):
        engine = self.listing(support.ENGINE, skip=(support.TESTS,))
        copy = self.listing(os.path.join(support.REPO, "skills", "vesta-init", "engine"))
        self.assertEqual(sorted(copy), sorted(engine), "run tools/build.py")
        for name in engine:
            self.assertEqual(copy[name], engine[name], name + " differs; run tools/build.py")


class SuiteStandsAlone(unittest.TestCase):
    def test_no_engine_source_reads_the_specification_folder(self):
        needles = [glue("sp", "ec/"), glue('"sp', 'ec"'), glue("'sp", "ec'")]
        for folder, names, leaves in os.walk(support.ENGINE):
            names[:] = [n for n in names if n not in ("__pycache__", "tests")]
            for leaf in leaves:
                if not leaf.endswith((".py", ".md")):
                    continue
                text = support.read(os.path.join(folder, leaf))
                for needle in needles:
                    self.assertFalse(needle in text, os.path.join(folder, leaf))

    def test_the_test_data_is_present(self):
        self.assertTrue(os.path.isfile(os.path.join(support.DATA, "sample-terms.txt")))
        for name, first in build.VERBATIM:
            text = support.read(os.path.join(support.DATA, "verbatim", name))
            self.assertTrue(text.startswith(first + "\n"), name)


if __name__ == "__main__":
    unittest.main()


class Release(unittest.TestCase):
    def test_the_tag_is_the_engines_version_and_another_is_refused(self):
        import contextlib
        import io
        release = support.tool("release")
        from kernel import version
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(release.main([]), 0)
            self.assertEqual(release.main(["--tag", "v" + version.ENGINE]), 0)
            self.assertEqual(release.main(["--tag", "v9.9.9"]), 1)
            self.assertEqual(release.main(["--tag", version.ENGINE]), 1)
            self.assertEqual(release.main(["--bogus"]), 2)
        self.assertEqual(out.getvalue().split("\n")[0], "v" + version.ENGINE)
        self.assertIn("the tag for it is v" + version.ENGINE, err.getvalue())
