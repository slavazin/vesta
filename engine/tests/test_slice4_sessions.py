import io
import json
import os
import re
import shutil
import subprocess
import sys
import unittest

import support
import fixtures
from fixtures import BODY, Project, decision
from adapters import git as git_source
from cli import manifest
from kernel.errors import Refusal
from matchers import grep, probes
from session import log, state

GOLDEN = os.path.join(support.TESTS, "golden")
SESSION = re.compile(r"S-[0-9]{8}-[0-9a-f]{4}")
SENTINEL = "ZZ-SENTINEL-ZZ"


def tokens(text, root):
    """A sheet with what changes from run to run replaced by fixed tokens."""
    return SESSION.sub("S-TOKEN", text.replace(root.replace("\\", "/"), "<root>"))


def mtime_config():
    config = fixtures.built_config()
    config["adapters"]["changes"] = "mtime"
    return config


def five(project):
    """Five decisions: two under src/http/, one with a trigger that has a probe, one retired."""
    project.write("src/http/client.py", "timeout = 10\n")
    project.put(decision("D-001", "0000000a", scopes=["src/http/"], when="calling an outside service"))
    project.put(decision("D-002", "0000000b", scopes=["docs/"], when="writing the user guide"))
    project.put(decision("D-003", "0000000c", when="naming a release", triggers=[
        {"id": "t1", "if": "the release notes file is gone", "then": "re-decide where releases are named", "probe": "missing docs/releases.md", "resolved": ""},
        {"id": "t2", "if": "a second product ships from this folder", "then": "check the naming still holds", "probe": "", "resolved": ""},
    ]))
    project.put(decision("D-004", "0000000d", scopes=["src/http/client.py"], when="choosing a timeout"))
    project.put(decision("D-005", "0000000e", status="retired", retired_because="the module was removed", scopes=["src/http/"]))


def session_of(project):
    return state.open_ones(project.context().tree)[0]


class StartWalk(unittest.TestCase):
    def test_records_the_paths_reach_are_printed_in_full_and_loaded_by_scope(self):
        with Project(init=True) as project:
            five(project)
            code, out, _ = project.run("walk", "start", "--ask", "raise the timeout", "--paths", "src/http/client.py")
            self.assertEqual(code, 0)
            for label in ("D-001", "D-004"):
                self.assertIn("---- %s, in full" % label, out)
            for label in ("D-002", "D-003", "D-005"):
                self.assertNotIn("---- %s, in full" % label, out)
            index = out.split("Index of the other records:")[1].split("## 2.")[0]
            self.assertIn("D-002  [docs/]", index)
            self.assertIn("D-003\n", index)
            self.assertNotIn("D-001", index)
            self.assertNotIn("D-005", out.replace("---- D-005", ""))
            loaded = session_of(project).loaded
            self.assertEqual([(entry["record"], entry["by"], entry["mark"]) for entry in loaded],
                             [("D-001@0000000a", "scope", ""), ("D-004@0000000d", "scope", "")])
            self.assertEqual(session_of(project).asks, ["raise the timeout"])

    def test_each_live_trigger_appears_once_and_its_probe_state_is_saved(self):
        with Project(init=True) as project:
            five(project)
            _, out, _ = project.run("walk", "start", "--paths", "docs/guide.md")
            self.assertEqual(out.count("D-003/t1"), 1)
            self.assertEqual(out.count("the release notes file is gone"), 1)
            self.assertEqual(out.count("a second product ships from this folder"), 1)
            self.assertIn("- **D-003/t1**, probe: fired", out)
            self.assertIn("- **D-003/t2**, probe: no probe", out)
            self.assertNotIn("unstable-if", out)
            self.assertEqual(session_of(project).probes, {"0000000c/t1": "fired", "0000000c/t2": "no probe"})

    def test_the_sheet_equals_the_golden_file(self):
        with Project(init=True) as project:
            five(project)
            _, out, _ = project.run("walk", "start", "--ask", "raise the timeout", "--paths", "src/http/client.py")
            path = os.path.join(GOLDEN, "start-sheet.md")
            if os.environ.get("VESTA_WRITE_GOLDEN"):
                support.write(path, tokens(out, project.root))
            self.assertTrue(os.path.isfile(path), "the golden file start-sheet.md is missing")
            self.assertEqual(tokens(out, project.root), support.read(path))

    def test_without_the_lenses_step_the_lens_section_is_gone_and_nothing_else_changes(self):
        def sections(out):
            """The sheet's sections by title, numbers left out."""
            found = {}
            for part in re.split(r"(?m)^## [0-9]+\. ", out.rsplit("\n---\n", 1)[0])[1:]:
                title, _, rest = part.partition("\n")
                found[title] = rest
            return found

        with Project(init=True) as project:
            five(project)
            _, whole, _ = project.run("walk", "start", "--paths", "src/http/client.py")
            project.run("session", "close")
            config = fixtures.built_config()
            config["checkpoints"]["start"]["steps"].remove("lenses")
            project.write_config(config)
            _, without, _ = project.run("walk", "start", "--paths", "src/http/client.py")
            first, second = sections(tokens(whole, project.root)), sections(tokens(without, project.root))
            self.assertIn("Lenses", first)
            self.assertNotIn("Lenses", second)
            del first["Lenses"]
            self.assertEqual(first, second)
            self.assertEqual(whole.rsplit("\n---\n", 1)[1], without.rsplit("\n---\n", 1)[1])

    def test_an_empty_rows_table_prints_no_section_and_an_empty_store_prints_none(self):
        with Project(init=True) as project:
            text = project.read("vesta/walks/start.md")
            row = [line for line in text.split("\n") if line.startswith("| start-01")][0]
            project.write("vesta/walks/start.md", text.replace(row + "\n", ""))
            _, out, _ = project.run("walk", "start")
            self.assertNotIn("Rows", out)
            self.assertIn("Steps of this walk: 1. Recall · 2. Triggers · 3. Lenses · 4. Notices", out)
            self.assertIn("## 1. Recall\n\n### decisions\n\nnone\n", out)
            self.assertIn("## 2. Triggers\n\nnone\n", out)

    def test_one_five_and_eight_lenses_are_printed_at_the_three_levels(self):
        def lenses(out):
            section = re.split(r"(?m)^## [0-9]+\. Lenses\n", out)
            return 0 if len(section) < 2 else len(re.findall(r"(?m)^- \*\*", re.split(r"(?m)^(## |---$)", section[1])[0]))

        counts = {}
        for level in ("quiet", "standard", "active"):
            config = fixtures.built_config()
            config["engagement"] = level
            with Project(init=True, config=config) as project:
                _, start, _ = project.run("walk", "start")
                _, close, _ = project.run("walk", "close")
                counts[level] = lenses(start) + lenses(close)
                if level == "quiet":
                    self.assertNotIn("two-readings", start + close)
                    self.assertNotIn("Lenses", start)
        self.assertEqual(counts, {"quiet": 1, "standard": 5, "active": 8})

    def test_the_instruction_names_fields_by_the_schema_and_takes_the_level_paragraph(self):
        with Project(init=True) as project:
            project.add_notes_store()
            _, out, _ = project.run("walk", "start")
            self.assertIn("whose `when` or `cue` line matches", out)
            self.assertIn("### notes", out)
            self.assertIn("Ask the owner a question only where two loaded records conflict or one reads false.", out)
            self.assertNotIn("[standard]", out)
            self.assertNotIn("Ask the owner nothing at this step", out)
            self.assertNotIn("{", out.split("---")[0].replace("{when}", ""))

    def test_a_step_this_engine_lacks_is_named_and_the_rest_prints(self):
        config = fixtures.built_config()
        config["checkpoints"]["start"]["steps"].insert(1, "horoscope")
        with Project(init=True, config=config) as project:
            code, out, _ = project.run("walk", "start")
            self.assertEqual(code, 0)
            self.assertIn("Not printed, because this engine has no such step: `horoscope`", out)
            self.assertIn("## 2. Triggers", out)

    def test_usage(self):
        with Project(init=True) as project:
            self.assertEqual(project.run("walk")[0], 2)
            code, _, err = project.run("walk", "finish")
            self.assertEqual(code, 2)
            self.assertIn("this project has: start, close, learn", err)
            code, _, err = project.run("walk", "start", "--from", "sweep")
            self.assertEqual(code, 2)
            self.assertIn("names no step of this walk", err)
            code, _, err = project.run("walk", "start", "--short", "--parallel")
            self.assertEqual(code, 2)
            self.assertIn("has no short form", err)


class SessionRules(unittest.TestCase):
    def test_a_second_start_is_refused_and_lists_the_open_session(self):
        with Project(init=True) as project:
            project.run("walk", "start", "--ask", "the first task")
            first = session_of(project).id
            before = project.files("vesta")
            code, out, _ = project.run("walk", "start", "--ask", "another")
            self.assertEqual(code, 3)
            self.assertIn(first, out)
            self.assertIn("task: the first task", out)
            for option in ("--continue", "--new", "--parallel", "walk close --short --session " + first):
                self.assertIn(option, out)
            self.assertIn("The rule is in vesta/INTERNALS.md, Sessions.", out)
            self.assertIn("## Sessions", project.read("vesta/INTERNALS.md"))
            self.assertEqual(project.files("vesta"), before)

    def test_continue_appends_the_ask_and_keeps_the_base(self):
        with Project(init=True) as project:
            project.run("walk", "start", "--ask", "one")
            base = session_of(project).base
            code, out, _ = project.run("walk", "start", "--continue", "--ask", "two")
            self.assertEqual(code, 0)
            session = session_of(project)
            self.assertEqual((session.asks, session.base), (["one", "two"], base))
            self.assertIn("Task: two", out)
            self.assertEqual(len(state.every(project.context().tree)), 1)

    def test_new_abandons_the_open_session_and_logs_its_records_unclosed(self):
        with Project(init=True) as project:
            five(project)
            project.run("walk", "start", "--paths", "src/http/client.py")
            first = session_of(project).id
            project.run("mark", "D-001=applied")
            code, out, _ = project.run("walk", "start", "--new", "--ask", "next")
            self.assertEqual(code, 0)
            tree = project.context().tree
            self.assertEqual(state.read(tree, first).status, "abandoned")
            self.assertNotEqual(session_of(project).id, first)
            lines = log.read(tree)
            self.assertEqual([(line["session"], line["record"], line["by"], line["mark"]) for line in lines],
                             [(first, "D-001@0000000a", "scope", "unclosed"), (first, "D-004@0000000d", "scope", "unclosed")])
            self.assertIn("marked abandoned", out)

    def test_with_two_open_a_command_without_the_session_is_refused(self):
        with Project(init=True) as project:
            five(project)
            project.run("walk", "start", "--ask", "one")
            first = session_of(project).id
            code, out, _ = project.run("walk", "start", "--parallel", "--ask", "two")
            self.assertEqual(code, 0)
            second = [s.id for s in state.open_ones(project.context().tree) if s.id != first][0]
            self.assertIn("--session " + second, out)
            for command in (("load", "D-001"), ("mark", "D-001=applied"), ("jot", "a note"), ("session", "show"), ("session", "close"), ("walk", "close")):
                code, out, _ = project.run(*command)
                self.assertEqual(code, 3, command)
                self.assertIn(first, out)
                self.assertIn(second, out)
            self.assertEqual(project.run("load", "D-001", "--session", second)[0], 0)
            tree = project.context().tree
            self.assertEqual(len(state.read(tree, second).loaded), 1)
            self.assertEqual(state.read(tree, first).loaded, [])
            code, _, err = project.run("load", "D-001", "--session", "S-20260101-ffff")
            self.assertEqual(code, 2)
            self.assertIn("is not a session of this project", err)

    def test_load_mark_and_close_write_the_log(self):
        with Project(init=True) as project:
            five(project)
            project.run("walk", "start", "--paths", "src/http/client.py")
            name = session_of(project).id
            code, out, _ = project.run("load", "D-002", "D-001")
            self.assertEqual(code, 0)
            self.assertIn("# Every figure is checked", out)
            self.assertIn("Loaded into %s: D-002." % name, out)
            self.assertIn("Already loaded, and left as first found: D-001.", out)
            self.assertEqual(project.run("load", "D-003", "--by", "trigger")[0], 0)
            self.assertEqual(project.run("load", "D-003", "--by", "scope")[0], 2)
            code, out, _ = project.run("mark", "D-005=applied")
            self.assertEqual(code, 3)
            self.assertIn("was not loaded", out)
            self.assertEqual(project.run("mark", "D-001=done")[0], 2)
            code, out, _ = project.run("mark", "D-001=applied", "D-002=not-applicable", "D-005=should-have-loaded")
            self.assertEqual(code, 0)
            self.assertIn("Loaded and not marked yet: D-004, D-003.", out)
            code, out, _ = project.run("session", "close")
            self.assertEqual(code, 0)
            self.assertIn("Logged as `unmarked`, since no mark was set: D-004, D-003.", out)
            tree = project.context().tree
            self.assertEqual(
                [(line["record"].split("@")[0], line["by"], line["mark"]) for line in log.read(tree)],
                [("D-001", "scope", "applied"), ("D-004", "scope", "unmarked"), ("D-002", "index", "not-applicable"),
                 ("D-003", "trigger", "unmarked"), ("D-005", "sweep", "should-have-loaded")],
            )
            self.assertEqual(set(log.read(tree)[0]), {"session", "at", "record", "by", "mark"})
            self.assertEqual(state.read(tree, name).status, "closed")
            self.assertEqual(project.run("session", "close", "--session", name)[0], 3)

    def test_a_session_that_loaded_nothing_logs_one_line_and_abandon_names_a_session(self):
        with Project(init=True) as project:
            project.run("walk", "start")
            name = session_of(project).id
            self.assertEqual(project.run("session", "abandon")[0], 2)
            code, out, _ = project.run("session", "abandon", name)
            self.assertEqual(code, 0)
            self.assertIn("marked abandoned", out)
            tree = project.context().tree
            self.assertEqual([(line["record"], line["by"], line["mark"]) for line in log.read(tree)], [("", "", "unclosed")])
            self.assertEqual(state.open_ones(tree), [])
            self.assertEqual(project.run("check")[0], 0)

    def test_a_session_file_that_does_not_read_is_named(self):
        with Project(init=True) as project:
            project.write("vesta/.state/sessions/S-20260105-0000.json", "{not json")
            self.assertEqual(project.run("walk", "start")[0], 0)
            code, _, err = project.run("session", "show", "--session", "S-20260105-0000")
            self.assertEqual(code, 2)
            self.assertIn("vesta/.state/sessions/S-20260105-0000.json does not read as a session", err)
            self.assertIn("A session file does not read: vesta/.state/sessions/S-20260105-0000.json", project.run("doctor")[1])


class Jots(unittest.TestCase):
    def test_a_jot_from_standard_input_is_kept_verbatim(self):
        text = 'she said "use $HOME/bin", not `~/bin`\nand a second line: 50% \\n done'
        with Project(init=True) as project:
            project.run("walk", "start")
            code, out, _ = project.run("jot", "--steer", "--anchor", "src/a.py", "-", stdin=io.StringIO(text + "\n"))
            self.assertEqual(code, 0)
            self.assertIn("as a correction from the owner", out)
            project.run("jot", "a plain note")
            jots = session_of(project).jots
            self.assertEqual([(jot["steer"], jot["text"], jot["anchor"]) for jot in jots],
                             [(True, text, "src/a.py"), (False, "a plain note", "")])
            _, shown, _ = project.run("session", "show")
            self.assertIn('[steer] she said "use $HOME/bin", not `~/bin`', shown)
            self.assertIn("(anchor: src/a.py)", shown)

    def test_the_real_command_line_reads_standard_input(self):
        text = 'quotes " and $VARS and `ticks`'
        with Project(init=True) as project:
            shutil.copytree(support.ENGINE, project.path("vesta/.engine"), ignore=shutil.ignore_patterns("tests", "__pycache__"))
            done = subprocess.run([sys.executable, project.path("vesta/.engine"), "jot", "-"], input=text.encode("utf-8"),
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=os.path.dirname(project.root))
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(session_of(project).jots[0]["text"], text)

    def test_a_jot_with_no_open_session_opens_a_late_one(self):
        with Project(init=True) as project:
            code, out, _ = project.run("jot", "noticed after the fact")
            self.assertEqual(code, 0)
            self.assertIn("was opened late", out)
            session = session_of(project)
            self.assertTrue(session.late)
            self.assertEqual(len(session.jots), 1)
            _, shown, _ = project.run("session", "show")
            self.assertIn("It was opened late", shown)
            self.assertEqual(project.run("jot", "  ")[0], 2)
            self.assertEqual(project.run("jot")[0], 2)


class Probes(unittest.TestCase):
    def evaluate(self, project, text):
        return probes.evaluate(text, project.context()).text()

    def test_each_form_fired_unfired_and_error(self):
        with Project(init=True) as project:
            project.write("docs/guide.md", "Install with pip.\nUse the old client here.\n")
            cases = [
                ("exists docs/guide.md", "fired"),
                ("exists docs/none.md", "unfired"),
                ("exists docs", "fired"),
                ("missing docs/none.md", "fired"),
                ("missing docs/guide.md", "unfired"),
                ('grep "old client" docs/guide.md', "fired"),
                ('grep "^Use the \\w+ client" docs/*.md', "fired"),
                ('grep "new client" docs/**', "unfired"),
                ('grep "old client" src/**/*.py', "unfired"),
                ("", "no probe"),
            ]
            for text, expected in cases:
                self.assertEqual(self.evaluate(project, text), expected, text)
            errors = [
                ("exists", "names no path"),
                ("touch docs/guide.md", "a probe opens with one of `exists`, `grep`, `missing`"),
                ('grep "(" docs/guide.md', "does not read as a regular expression"),
                ("grep old docs/guide.md", "between double quotes"),
                ('grep "%s" docs/guide.md' % ("a" * 201), "the most is 200"),
                ('grep "old" docs/none.md', "there is no `docs/none.md` to read"),
            ]
            for text, expected in errors:
                found = self.evaluate(project, text)
                self.assertTrue(found.startswith("error: "), found)
                self.assertIn(expected, found)

    def test_a_path_leaving_the_root_is_refused(self):
        with Project(init=True) as project:
            for text in ("exists ../outside.txt", "missing /etc/passwd", 'grep "x" ../**'):
                found = self.evaluate(project, text)
                self.assertTrue(found.startswith("error: "), found)
                self.assertIn("leaves the project", found)
            outside = os.path.join(os.path.dirname(project.root), "outside-" + os.path.basename(project.root))
            os.makedirs(outside)
            try:
                support.write(os.path.join(outside, "secret.txt"), "the old client\n")
                try:
                    os.symlink(outside, project.path("linked"))
                except (OSError, NotImplementedError):
                    self.skipTest("this platform does not let the test make a link")
                for text in ("exists linked/secret.txt", 'grep "old client" linked/secret.txt'):
                    found = self.evaluate(project, text)
                    self.assertTrue(found.startswith("error: "), found)
                    self.assertIn("leads outside the project through a link", found)
                self.assertEqual(self.evaluate(project, 'grep "old client" **/*.txt'), "unfired (1 file skipped as too large, not text, or outside the project)")
            finally:
                shutil.rmtree(outside)

    def test_grep_skips_large_files_ignored_folders_and_files_that_are_not_text(self):
        with Project(init=True) as project:
            project.write("data/big.txt", "old client\n" + "x" * (1024 * 1024))
            project.write("node_modules/pkg/a.txt", "old client\n")
            with open(project.path("data/blob.txt"), "wb") as handle:
                handle.write(b"old client \xff\xfe\n")
            project.write("data/long.txt", " " * 2000 + "old client\n")
            self.assertEqual(self.evaluate(project, 'grep "old client" **/*.txt'), "unfired (2 files skipped as too large, not text, or outside the project)")
            project.write("data/small.txt", "old client\n")
            self.assertTrue(self.evaluate(project, 'grep "old client" data/**').startswith("fired"))

    def test_past_the_file_limit_the_probe_reports_an_error(self):
        with Project(init=True) as project:
            for number in range(6):
                project.write("many/%d.txt" % number, "x\n")
            before = grep.MAX_FILES
            grep.MAX_FILES = 5
            try:
                found = self.evaluate(project, 'grep "x" many/*.txt')
            finally:
                grep.MAX_FILES = before
            self.assertTrue(found.startswith("error: the probe reaches more than 5 files"), found)
            self.assertEqual(before, 2000)

    def test_the_probes_check(self):
        with Project(init=True) as project:
            project.put(decision("D-001", "0000000a", triggers=[
                {"id": "t1", "if": "the guide is gone", "then": "check the links", "probe": "missing docs/guide.md", "resolved": ""},
                {"id": "t2", "if": "handled before", "then": "check", "probe": "missing docs/guide.md", "resolved": "P-003"},
                {"id": "t3", "if": "something else", "then": "check", "probe": "glance docs", "resolved": ""},
            ]))
            found = project.check()
            self.assertEqual(len(found), 2, found)
            self.assertIn("error probes vesta/decisions/D-001.md", found[0] if "error" in found[0] else found[1])
            self.assertTrue(any("the probe of D-001/t3 does not read" in line for line in found))
            self.assertTrue(any(line.startswith("warning probes") and "D-001/t1 fires" in line for line in found))
            _, out, _ = project.run("check")
            self.assertIn("- `probes`: not whether an `if` that has no probe holds", out)

    def test_the_triggers_command_lists_each_live_trigger_and_saves_nothing(self):
        with Project(init=True) as project:
            five(project)
            before = project.files("vesta")
            code, out, _ = project.run("triggers")
            self.assertEqual(code, 0)
            self.assertIn("- **D-003/t1**, probe: fired", out)
            self.assertIn("  then: re-decide where releases are named", out)
            self.assertEqual(project.files("vesta"), before)


class RowMatch(unittest.TestCase):
    def test_a_row_with_globs_is_fired_by_a_matching_path_and_judged_otherwise(self):
        with Project(init=True) as project:
            text = project.read("vesta/walks/start.md")
            head = "|---|---|---|---|---|---|---|\n"
            project.write("vesta/walks/start.md", text.replace(head, head + "| start-02 | a report is being sent | `reports/**/*.md`, `out/*.pdf` | `docs/sending.md` | read the sending list | quiet | seed |\n", 1))
            _, out, _ = project.run("walk", "start", "--paths", "reports/2026/q1.md")
            self.assertIn("- **start-02** (fired)", out)
            self.assertIn("- **start-01** (judge)", out)
            project.run("session", "close")
            _, out, _ = project.run("walk", "start", "--paths", "src/a.py")
            self.assertIn("- **start-02** (judge)", out)


def git(root, *arguments):
    done = subprocess.run(["git", "-C", root] + list(arguments), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert done.returncode == 0, done.stderr
    return done.stdout.decode("utf-8")


def changed(project):
    context = project.context()
    return state.changed(context, state.every(context.tree)[-1])


@unittest.skipUnless(shutil.which("git"), "no git program on this machine")
class GitSource(unittest.TestCase):
    def repository(self, project):
        git(project.root, "init", "-q")
        git(project.root, "config", "user.email", "tester@example.com")
        git(project.root, "config", "user.name", "Tester")
        project.write("src/kept.txt", "kept\n")
        project.write("src/edited.txt", "one\n")
        project.write("src/already.txt", "one\n")
        git(project.root, "add", "-A")
        git(project.root, "commit", "-q", "-m", "first")

    def test_what_was_already_changed_is_not_reported_unless_it_changes_again(self):
        with Project(init=True) as project:
            self.repository(project)
            project.write("src/already.txt", "modified before the session\n")
            project.write("notes.txt", "untracked before the session\n")
            project.run("walk", "start")
            base = session_of(project).base
            self.assertEqual(base["source"], "git")
            self.assertEqual(sorted(base["dirty"]), ["notes.txt", "src/already.txt"])
            self.assertEqual(changed(project), ([], ""))
            project.write("src/edited.txt", "two\n")
            project.write("src/new.txt", "new\n")
            os.remove(project.path("src/kept.txt"))
            self.assertEqual(changed(project), (["src/edited.txt", "src/kept.txt", "src/new.txt"], ""))
            later = os.stat(project.path("notes.txt")).st_mtime_ns + 5 * 10 ** 9
            project.write("notes.txt", "changed during the session\n")
            os.utime(project.path("notes.txt"), ns=(later, later))
            self.assertIn("notes.txt", changed(project)[0])
            git(project.root, "add", "-A")
            git(project.root, "commit", "-q", "-m", "second")
            self.assertEqual(changed(project)[0], ["notes.txt", "src/edited.txt", "src/kept.txt", "src/new.txt"])

    def test_a_file_the_engine_wrote_is_not_reported_and_ignored_folders_are_skipped(self):
        with Project(init=True) as project:
            self.repository(project)
            project.run("walk", "start")
            name = session_of(project).id
            project.write("node_modules/pkg/index.js", "x\n")
            project.write("src/new.txt", "new\n")
            project.run("session", "close")
            session = state.read(project.context().tree, name)
            self.assertIn("vesta/log/consultations.jsonl", session.written)
            self.assertEqual(changed(project), (["src/new.txt"], ""))
            _, out, _ = project.run("session", "show", "--session", name)
            self.assertIn("- src/new.txt", out)
            self.assertNotIn("consultations.jsonl", out)
            self.assertNotIn(".state", out)

    def test_a_project_inside_a_larger_repository_reports_only_its_own_paths(self):
        with Project(init=True) as project:
            outer = os.path.dirname(project.root)
            inner = os.path.join(project.root, "inner")
            shutil.copytree(project.path("vesta"), os.path.join(inner, "vesta"))
            git(project.root, "init", "-q")
            git(project.root, "config", "user.email", "tester@example.com")
            git(project.root, "config", "user.name", "Tester")
            git(project.root, "add", "-A")
            git(project.root, "commit", "-q", "-m", "first")
            from cli import main
            out = io.StringIO()
            self.assertEqual(main.main(["walk", "start"], root=inner, clock=project.clock, out=out, err=io.StringIO()), 0)
            support.write(os.path.join(inner, "a.txt"), "x\n")
            project.write("outside-the-project.txt", "x\n")
            from cli import build
            context = build.context(inner, io.StringIO(), project.clock)
            self.assertEqual(state.changed(context, state.open_ones(context.tree)[0]), (["a.txt"], ""))
            self.assertTrue(outer)

    def test_with_a_repository_and_no_git_program_auto_falls_back_and_doctor_says_so(self):
        with Project(init=True) as project:
            self.repository(project)
            before = git_source.PROGRAM
            git_source.PROGRAM = "git-that-is-not-installed"
            try:
                code, out, _ = project.run("doctor")
                self.assertEqual(code, 0)
                self.assertIn("- Changed files are found by: mtime (`git` is not used: the project is inside a git repository and no `git-that-is-not-installed` program was found)", out)
                project.run("walk", "start")
                self.assertEqual(session_of(project).base["source"], "mtime")
                config = fixtures.built_config()
                config["adapters"]["changes"] = "git"
                project.write_config(config)
                code, out, _ = project.run("walk", "start", "--new")
                self.assertEqual(code, 0)
                self.assertIn("The files this session changes will not be known: `git` cannot be used to find changed files", out)
                _, out, _ = project.run("session", "show")
                self.assertIn("could not be read: `git` cannot be used", out)
                _, out, _ = project.run("doctor")
                self.assertIn("- Changed files cannot be found: `git` cannot be used", out)
            finally:
                git_source.PROGRAM = before


class MtimeSource(unittest.TestCase):
    def test_a_file_changed_after_the_base_is_reported_and_ignored_folders_are_skipped(self):
        with Project(init=True, config=mtime_config()) as project:
            project.write("src/old.txt", "old\n")
            project.run("walk", "start")
            session = session_of(project)
            self.assertEqual(session.base["source"], "mtime")
            at = session.base["at"]
            for path in project.files():
                os.utime(project.path(path), ns=(at - 10 ** 9, at - 10 ** 9))
            self.assertEqual(changed(project), ([], ""))
            for path in ("src/new.txt", "node_modules/pkg/a.js", ".git/index", "vesta/.engine/x.py", "vesta/decisions/D-009.md"):
                project.write(path, "x\n")
                os.utime(project.path(path), ns=(at + 10 ** 9, at + 10 ** 9))
            os.utime(project.path("src/old.txt"), ns=(at + 10 ** 9, at + 10 ** 9))
            self.assertEqual(changed(project), (["src/new.txt", "src/old.txt", "vesta/decisions/D-009.md"], ""))
            project.run("jot", "a note")
            project.run("session", "close")
            found = changed(project)[0]
            self.assertNotIn("vesta/log/consultations.jsonl", found)
            self.assertFalse([path for path in found if path.startswith("vesta/.state")])

    def test_doctor_lists_a_session_that_is_not_closed(self):
        with Project(init=True, config=mtime_config()) as project:
            project.run("walk", "start", "--ask", "tidy the export")
            project.run("jot", "one")
            project.clock.advance(seconds=3 * 3600)
            _, out, _ = project.run("doctor")
            self.assertIn("- Sessions not closed: 1", out)
            self.assertIn("1 jot, task: tidy the export; age: 3 hours", out)
            self.assertIn("session abandon <id>", out)


class ZeroCost(unittest.TestCase):
    def test_a_member_the_configuration_does_not_name_is_never_imported_by_a_walk(self):
        folder = os.path.join(support.ENGINE, "steps")
        names = {"steps": "steps.fixture_unnamed_step", "kinds": "proposals.fixture_unnamed_kind"}
        tables = {"steps": manifest.STEPS, "kinds": manifest.KINDS}
        for table, module in names.items():
            tables[table]["fixture-unnamed"] = module
        try:
            with Project(init=True) as project:
                five(project)
                config = project.read("vesta/vesta.yml")
                self.assertNotIn("fixture-unnamed", config)
                before = set(project.files())
                for command in (("walk", "start", "--paths", "src/http/client.py"), ("walk", "close"), ("walk", "learn"), ("session", "show"), ("check",)):
                    code, _, err = project.run(*command)
                    self.assertIn(code, (0, 1), err)
                for module in names.values():
                    self.assertNotIn(module, sys.modules)
                self.assertFalse([path for path in set(project.files()) - before if "fixture" in path])
                self.assertEqual(project.run("check")[0], 0)
        finally:
            for table in tables.values():
                del table["fixture-unnamed"]
        self.assertTrue(os.path.isdir(folder))

    def test_only_the_configured_steps_and_probes_in_use_are_imported(self):
        for name in list(sys.modules):
            if name.startswith(("steps.", "matchers.")) and name.rsplit(".", 1)[1] in ("bundle", "grep", "exists", "missing", "notices"):
                del sys.modules[name]
        config = fixtures.built_config()
        config["checkpoints"]["start"]["steps"].remove("notices")
        with Project(init=True, config=config) as project:
            project.put(decision("D-001", "0000000a", triggers=[{"id": "t1", "if": "x", "then": "check", "probe": "exists src", "resolved": ""}]))
            self.assertEqual(project.run("walk", "start")[0], 0)
            self.assertIn("matchers.exists", sys.modules)
            for module in ("steps.bundle", "steps.notices", "matchers.grep", "matchers.missing"):
                self.assertNotIn(module, sys.modules)

    def test_the_start_sheet_prints_no_observation_and_evaluates_none_of_their_probes(self):
        with Project(init=True) as project:
            five(project)
            project.write("vesta/observations/open/O-20260105-0000aaaa.md", "---\n" + "\n".join([
                "uid: 0000aaaa", "id: O-20260105-0000aaaa", "date: 2026-01-05", "session: S-20260105-0000", "via: off-map",
                "anchor: src/a.py", "recheck: exists %s" % SENTINEL, "disposition: open", "held: []",
            ]) + "\n---\n# %s title\n\n%s body\n" % (SENTINEL, SENTINEL))
            seen = []
            real = probes.evaluate

            def watching(text, context):
                seen.append(text)
                return real(text, context)

            probes.evaluate = watching
            try:
                _, start, _ = project.run("walk", "start", "--paths", "src/http/client.py")
                _, close, _ = project.run("walk", "close")
            finally:
                probes.evaluate = real
            self.assertNotIn(SENTINEL, start + close)
            self.assertTrue(seen)
            self.assertFalse([text for text in seen if SENTINEL in str(text)])


class AfterTheReview(unittest.TestCase):
    def repository(self, project):
        return GitSource.repository(self, project)

    def test_what_was_staged_before_the_session_is_not_a_change_and_a_revert_is(self):
        if shutil.which("git") is None:
            self.skipTest("no git program")
        with Project(init=True) as project:
            for name in ("a.txt", "b.txt", "c.txt", "d.txt"):
                project.write(name, "1\n")
            self.repository(project)
            project.write("a.txt", "2\n")
            project.write("d.txt", "2\n")
            project.write("new.txt", "x\n")
            project.write("loose.txt", "x\n")
            git(project.root, "rm", "-q", "c.txt")
            git(project.root, "add", "a.txt", "new.txt")
            project.run("walk", "start")
            self.assertEqual(changed(project), ([], ""))
            git(project.root, "checkout", "-q", "--", "d.txt")
            os.remove(project.path("loose.txt"))
            self.assertEqual(changed(project), (["d.txt", "loose.txt"], ""))

    def test_a_path_given_from_the_file_system_root_is_read_against_the_project(self):
        with Project(init=True) as project:
            five(project)
            _, out, _ = project.run("walk", "start", "--paths", project.path("src/http/client.py"), "src/../docs/guide.md", "../elsewhere/a.py", "/nowhere/b.py")
            for label in ("D-001", "D-002", "D-004"):
                self.assertIn("---- %s, in full" % label, out)
            self.assertIn("Paths given: `src/http/client.py`, `docs/guide.md`", out)
            self.assertIn("`../elsewhere/a.py` is not inside the project", out)
            self.assertIn("`/nowhere/b.py` is not inside the project", out)

    def test_a_linked_folder_is_not_walked(self):
        with Project(init=True, config=mtime_config()) as project:
            project.write("src/a.py", "TODO\n")
            try:
                os.symlink(project.root, project.path("loop"))
            except (OSError, NotImplementedError):
                self.skipTest("links cannot be made here")
            project.run("walk", "start")
            at = session_of(project).base["at"] + 10 ** 9
            os.utime(project.path("src/a.py"), ns=(at, at))
            self.assertEqual(changed(project), (["src/a.py"], ""))
            found = probes.evaluate('grep "TODO" **/*.py', project.context())
            self.assertEqual(found.state, probes.FIRED)

    def test_what_the_engine_wrote_for_one_session_is_no_change_of_another(self):
        with Project(init=True, config=mtime_config()) as project:
            project.put(decision("D-001", "0000000a"))
            project.run("walk", "start", "--ask", "first")
            first = session_of(project).id
            _, out, _ = project.run("walk", "start", "--parallel", "--ask", "second")
            second = [name for name in SESSION.findall(out) if name != first][0]
            project.run("session", "close", "--session", second)
            _, shown, _ = project.run("session", "show", "--session", first)
            self.assertNotIn("consultations.jsonl", shown)
            self.assertNotIn(".state", shown)

    def test_a_walk_that_cannot_print_changes_nothing(self):
        with Project(init=True) as project:
            project.run("walk", "start", "--ask", "one")
            first = session_of(project).id
            for arguments in (("--new", "--from", "zzz"), ("--new", "--with", "zzz"), ("--new", "--short")):
                code, _, err = project.run("walk", "start", "--ask", "two", *arguments)
                self.assertEqual(code, 2, arguments)
            self.assertEqual([session.id for session in state.open_ones(project.context().tree)], [first])
            code, _, err = project.run("walk", "close", "--new")
            self.assertEqual(code, 2)
            self.assertIn("`--new` is not an option of this command", err)

    def test_a_closed_session_takes_no_mark_and_a_loaded_record_is_not_marked_as_missed(self):
        with Project(init=True) as project:
            five(project)
            project.run("walk", "start", "--paths", "src/http/client.py")
            session = session_of(project).id
            code, out, _ = project.run("mark", "D-001=should-have-loaded")
            self.assertEqual(code, 3)
            self.assertIn("was loaded in", out)
            project.run("session", "close")
            for command in (("mark", "D-001=applied"), ("jot", "late"), ("load", "D-002")):
                code, out, _ = project.run(*command, "--session", session)
                self.assertEqual(code, 3, command)
                self.assertIn("The rule is in vesta/INTERNALS.md, Sessions", out)

    def test_a_grep_probe_does_not_read_a_skipped_folder_or_one_reached_through_a_link(self):
        with Project(init=True) as project:
            project.write("node_modules/pkg/a.js", "TODO\n")
            found = probes.evaluate('grep "TODO" node_modules/**', project.context())
            self.assertEqual(found.state, probes.ERROR)
            self.assertIn("changes.ignore", found.reason)
            outside = os.path.join(os.path.dirname(project.root), "outside-" + os.path.basename(project.root))
            os.makedirs(outside)
            try:
                support.write(os.path.join(outside, "a.txt"), "TODO\n")
                try:
                    os.symlink(outside, project.path("out_link"))
                except (OSError, NotImplementedError):
                    self.skipTest("links cannot be made here")
                found = probes.evaluate('grep "TODO" out_link/**', project.context())
                self.assertEqual(found.state, probes.ERROR)
                self.assertIn("outside the project", found.reason)
            finally:
                shutil.rmtree(outside)

    def test_jots_sent_at_once_all_land(self):
        import threading
        with Project(init=True) as project:
            project.run("walk", "start")
            results = []
            threads = [threading.Thread(target=lambda number=number: results.append(project.run("jot", "note %d" % number))) for number in range(12)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            # Every jot that said it was written is there: none is dropped in silence.
            codes = [code for code, _, _ in results]
            self.assertEqual(len(session_of(project).jots), codes.count(0))
            self.assertEqual(codes.count(0), 12, [out + err for code, out, err in results if code])

    def test_a_session_is_not_written_without_its_lock(self):
        from session import state
        from kernel import tree as trees
        with Project(init=True) as project:
            project.run("walk", "start")
            lock = project.path(state.LOCK)
            support.write(lock, "")
            real = trees.LOCK_PATIENCE
            trees.LOCK_PATIENCE = 0.05
            try:
                code, out, err = project.run("jot", "a note while another command holds the session")
            finally:
                trees.LOCK_PATIENCE = real
                os.remove(lock)
            self.assertEqual(code, 2, out + err)
            self.assertIn("nothing was written. Run this command again", err)
            self.assertEqual(session_of(project).jots, [])

    def test_standard_input_that_is_not_utf8_is_named(self):
        with Project(init=True) as project:
            shutil.copytree(support.ENGINE, project.path("vesta/.engine"), ignore=shutil.ignore_patterns("tests", "__pycache__"))
            command = [sys.executable, project.path("vesta/.engine"), "jot", "-"]
            env = dict(os.environ, PYTHONIOENCODING="cp1252")
            done = subprocess.run(command, input=b"caf\xff", stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
            self.assertEqual(done.returncode, 2)
            self.assertIn(b"standard input is not UTF-8", done.stderr)
            done = subprocess.run(command, input="caf\u00e9".encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(session_of(project).jots[0]["text"], "caf\u00e9")

    def test_continue_keeps_the_probe_states_of_the_first_start(self):
        with Project(init=True) as project:
            five(project)
            project.run("walk", "start")
            project.write("docs/releases.md", "x\n")
            project.run("walk", "start", "--continue")
            _, out, _ = project.run("session", "show")
            self.assertIn("D-003/t1: fired at the start, now unfired", out)


class HookSkill(unittest.TestCase):
    def test_the_skill_names_only_commands_the_engine_has(self):
        text = " ".join(support.read(os.path.join(support.REPO, "skills", "vesta-hook", "SKILL.md")).split())
        used = set(re.findall(r"`vesta ([a-z]+)", text))
        self.assertEqual(used - set(manifest.COMMANDS), set())
        self.assertTrue({"walk", "version"} <= used)
        for phrase in ("Nothing forces this skill to be run", "carried out honestly", "cannot tell whether the owner approved it", "--continue", "--new", "walk close --short --session"):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
