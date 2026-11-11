import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

import support
import fixtures
from fixtures import Project, decision
from kernel import shipped as shipping
from session import state
from test_slice5_close import LABEL, add
from test_slice6_proposals import front, propose
from test_slice7_learn import fields_of, learn, section, shipped

PROJECTS = os.path.join(support.TESTS, "projects")
BUILT = os.path.join(support.REPO, "skills", "vesta-init", "engine")
HIDDEN = re.compile(r"\b(latch|walk|row|lens|lenses|bar|ladder|sweep|bundle)(s|ed|es)?\b", re.I)
INTERNAL = re.compile(r"@|\b[0-9a-f]{8}\b")
# Every word the sheets tell the agent to leave out when it speaks to the owner.
BANNED = re.compile(r"\b(latch|walk|row|lens|lenses|bar|ladder|sweep|bundle|trigger|index|mark|window|held)(s|ed|es)?\b", re.I)


def draft(spec):
    body = "# %s\n\n## Context\n%s\n\n## Decision\n%s.\n\n## Warrant\n- False if: %s.\n" % (spec["title"], spec["context"], spec["title"], spec["false-if"])
    return front(decision("NEW", "NEW", decided="", approved_by="", when=spec["when"], why=spec["why"], scopes=spec["scopes"])) + body


class Run(object):
    """The scripted run: the agent's judgment replaced by the fixed inputs of a fixture's script."""

    def __init__(self, case, project, name):
        self.case, self.project = case, project
        self.script = json.loads(support.read(os.path.join(PROJECTS, name, "script.json")))
        for folder, _, leaves in os.walk(os.path.join(PROJECTS, name)):
            for leaf in leaves:
                if leaf != "script.json":
                    full = os.path.join(folder, leaf)
                    project.write(os.path.relpath(full, os.path.join(PROJECTS, name)).replace(os.sep, "/"), support.read(full))
        self.said = []  # what the owner is told, in order

    def run(self, *arguments, **options):
        code, out, err = self.project.run(*arguments, **options)
        self.case.assertEqual(code, 0, "%s\n%s%s" % (" ".join(arguments), out, err))
        return out

    def passes(self, step):
        code, out, _ = self.project.run("check")
        self.case.assertEqual(code, 0, "check after %s:\n%s" % (step, out))

    def titled(self, label):
        store = self.project.store("decisions")
        return "%s, %s" % (label, store.title(store.get(label)))

    def put(self, label, title, cost):
        self.said.append("Proposed: %s. From now on: %s. Approve %s?" % (title, cost, label))

    def decide(self, spec, source, evidence=None):
        label = propose(self.project, "add", "decisions", draft=draft(spec), evidence=evidence, title="Record that %s" % spec["title"][0].lower() + spec["title"][1:], source=source)
        listed = [line for line in self.run("proposals").split("\n") if line.startswith("- %s " % label)][0]
        self.put(label, listed.split(" · ")[2], listed.split("standing cost: ")[1].split(" · ")[0])
        return self.run("apply", label)

    def session(self, part, applied=()):
        """One session: the start, the work, the close. Returns the labels of the notes it wrote."""
        sheet = self.run("walk", "start", "--ask", part["task"], "--paths", *part["paths"])
        name = state.open_ones(self.project.context().tree)[0]
        loaded = [entry["record"].split("@")[0] for entry in name.loaded]
        notices = [line for line in section(sheet, "Notices").split("**Do:**")[0].split("\n") if line.strip() and line.strip() != "none"]
        self.said.append("Before this task: %s. %s" % (
            "; ".join(self.titled(label) for label in loaded) or "nothing decided earlier bears on it",
            " ".join("%s notes have built up; `/vesta-learn` would go through them." % re.search(r"(\d+) notes", line).group(1) for line in notices if "notes are open" in line) or "Nothing is waiting for you.",
        ))
        if applied:
            self.run("mark", *["%s=applied" % label for label in applied])
        if part.get("change"):
            self.project.write(part["change"], self.project.read(part["change"]) + "\nchanged\n")
            at = name.base["at"] + 10 ** 9
            os.utime(self.project.path(part["change"]), ns=(at, at))
        self.project.clock.advance(seconds=30)
        self.run("walk", "close")
        labels = []
        if part.get("notes"):
            labels = LABEL.findall(self.run("obs", "add", stdin=io.StringIO(json.dumps(part["notes"]))))
        self.run("session", "close")
        self.run("walk", "close", "--from", "choices", "--session", name.id)
        self.said.append("Done. %s I wrote %d note%s: %s. Nothing is waiting for your decision." % (
            " ".join("I applied %s." % self.titled(label) for label in applied) or "No earlier decision bore on it.",
            len(labels), "" if len(labels) == 1 else "s", "; ".join(note["title"] for note in part.get("notes", [])) or "none",
        ))
        self.project.clock.advance(days=1)
        return sheet, labels


class ExitTest(unittest.TestCase):
    def scripted(self, name):
        config = shipped()
        config["reminders"]["learn"]["open-observations"] = 2
        with Project(init=True, config=config) as project:
            run = Run(self, project, name)
            script = run.script
            run.passes("init")
            # 1. One decision from an owner statement.
            run.decide(script["first"], "init")
            run.passes("the first decision")
            self.assertIn("source: init", project.read("vesta/log/proposals/P-001.md"))
            # 2. Session A reads it, applies it and writes two notes.
            sheet, first = run.session(script["a"], applied=["D-001"])
            self.assertIn("---- D-001, in full", sheet)
            self.assertIn(script["first"]["title"], sheet)
            self.assertEqual(len(first), 2)
            marks = [json.loads(line) for line in project.read("vesta/log/consultations.jsonl").split("\n") if line.strip()]
            self.assertEqual([(entry["record"].split("@")[0], entry["mark"]) for entry in marks], [("D-001", "applied")])
            steer = fields_of(project, "vesta/observations/open/%s.md" % first[1])
            self.assertEqual((steer["via"], steer["missed-by"]), ("owner-steer", "none"))
            run.passes("session A")
            # 3. Session B writes a note of the same shape as that steer.
            _, second = run.session(script["b"])
            self.assertEqual(fields_of(project, "vesta/observations/open/%s.md" % second[0])["via"], "owner-steer")
            run.passes("session B")
            # 4. A pass: three notes from two sessions; the two of one shape become a decision; the third is held.
            window = section(learn(project), "Window")
            self.assertIn("pass-001 reads 3 notes, from 2 sessions.", window)
            out = run.decide(script["second"], "pass-001", evidence=[first[1], second[0]])
            self.assertIn("The new record is D-002.", out)
            self.assertIn("source: pass-001", project.read("vesta/log/proposals/P-002.md"))
            run.passes("the approval")
            learn(project, "--from", "gate")
            learn(project, "--from", "seal")
            note = run.run("pass", "seal", "--note", "-", stdin=io.StringIO("Groups: 1\nUngrouped: 1\nNot done: nothing\nWaiting %s: a second session\n" % first[0]))
            self.assertIn("- Proposals: P-002 add → D-002 approved", note)
            run.said.append("I went through 3 notes from 2 sessions. One group became %s, which you approved. One note is kept until it is seen a second time." % run.titled("D-002"))
            run.passes("the pass")
            # 5. Session C sees the new decision; the held note is open; the promoted two are archived.
            sheet, _ = run.session(script["c"])
            block = sheet.split("Index of the other records:")[1].split("## 2.")[0]
            self.assertIn("D-002", block)
            self.assertIn(script["second"]["when"], block)
            self.assertEqual(sorted(os.listdir(project.path("vesta/observations/open"))), ["%s.md" % first[0]])
            self.assertEqual(sorted(os.listdir(project.path("vesta/observations/archive/pass-001"))), sorted("%s.md" % label for label in (first[1], second[0])))
            for label in (first[1], second[0]):
                self.assertEqual(fields_of(project, "vesta/observations/archive/pass-001/%s.md" % label)["disposition"], "promoted → D-002 (P-002)")
            run.passes("session C")
            # 6. Two approvals, and no more, are on record.
            lines = [line for line in project.read("vesta/log/admissions.md").split("\n") if line.startswith("- ")]
            self.assertEqual(len(lines), 2, lines)
            self.assertTrue(all("· approved" in line for line in lines))
            return run.said

    def test_the_scripted_run_passes_on_the_software_project(self):
        said = self.scripted("software")
        self.assertTrue(any("notes have built up" in line for line in said), said)
        self.assertEqual(len([line for line in said if line.startswith("Proposed:")]), 2)

    def test_the_same_script_passes_on_a_project_that_is_not_software(self):
        self.scripted("office")

    def test_nothing_the_owner_is_told_uses_a_word_of_the_mechanism_or_an_internal_id(self):
        for name in ("software", "office"):
            for line in self.scripted(name):
                self.assertIsNone(HIDDEN.search(line), line)
                self.assertIsNone(INTERNAL.search(line), line)

    def test_no_instruction_has_the_agent_say_a_word_of_the_mechanism_to_the_owner(self):
        """Every sentence, in a step text or a skill, that has the agent tell the owner something."""
        said = re.compile(
            r"\b(tell|say|give|report|put|show|ask|mention|name)s?\b[^.]*\b(the owner|them|the owner's)\b"
            r"|\bthe owner\b[^.]*\bis told\b|\b(brief|report)\b[^.]*\bto the owner\b", re.I,
        )
        files = [os.path.join(support.ENGINE, "steps", "text", leaf) for leaf in sorted(os.listdir(os.path.join(support.ENGINE, "steps", "text")))]
        files += [os.path.join(support.REPO, "skills", name, "SKILL.md") for name in sorted(os.listdir(os.path.join(support.REPO, "skills")))
                  if os.path.isdir(os.path.join(support.REPO, "skills", name))]
        files.append(os.path.join(support.ENGINE, "templates", "pointer-block.md"))
        self.assertTrue(len(files) > 20)

        def offences(text):
            found = []
            for sentence in re.split(r"(?<=[.:;])\s+", " ".join(text.split())):
                bare = re.sub(r"`[^`]*`", "", sentence)
                if "eave out" not in bare and said.search(bare) and (BANNED.search(bare) or INTERNAL.search(bare)):
                    found.append(sentence)
            return found

        # The test catches what it is for: each of these would have the agent say the word.
        for planted in (
            "Then tell them which row fired, by its id.", "It tells the owner the lens name and the latch.",
            "Mention the sweep and the bundle O-20261110-21a61661 in the brief to the owner.", "Tell the owner the uid 21a61661 of the note.",
            "Say to the owner that the index was read.", "Report to the owner each note held in the window.",
        ):
            self.assertEqual(offences(planted), [planted])
        for path in files:
            self.assertEqual(offences(support.read(path)), [], os.path.basename(os.path.dirname(path)) + "/" + os.path.basename(path))
        for leaf in ("after-start.md", "after-close.md", "after-learn.md"):
            text = " ".join(support.read(os.path.join(support.ENGINE, "steps", "text", leaf)).split())
            self.assertNotIn("the index was read", text)
            if leaf != "after-start.md":
                self.assertIn("a note by its title", text)
                self.assertNotIn("labels and titles", text)

    def test_the_cost_every_kind_of_proposal_states_is_in_plain_words(self):
        """The cost line is put to the owner as it is printed."""
        import ast
        from cli import manifest
        modules = sorted(set(manifest.KINDS.values()) | {"proposals.records"})
        costly = re.compile(r"^(none\b|one\b|\d|%d)|\bat every\b|\beach time\b|\bfewer\b|\bmore\b", re.I)
        found = []
        for name in modules:
            tree = ast.parse(support.read(os.path.join(support.ENGINE, *name.split(".")) + ".py"))
            inside = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name in ("standing_cost", "cost"):
                    inside.update(id(each) for each in ast.walk(node))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and " " in node.value:
                    # Any string in a cost function, and any string anywhere in the module that reads as a cost.
                    if (id(node) in inside and not node.value.startswith("What ")) or costly.search(node.value) and not node.value.rstrip().endswith('"""'):
                        found.append((name, node.value))
        self.assertTrue(len([text for _, text in found if text.startswith(("none", "one"))]) >= 8, found)
        for name, text in found:
            if "\n" in text.strip() or text[:1].isupper() and not costly.match(text):
                continue  # a docstring or a refusal, not a cost
            bare = re.sub(r"`[^`]*`", "", text)
            self.assertIsNone(BANNED.search(bare), "%s: %s" % (name, text))
            self.assertIsNone(INTERNAL.search(bare), "%s: %s" % (name, text))

    def test_the_reports_the_sheets_ask_for_are_in_plain_words(self):
        folder = os.path.join(support.ENGINE, "steps", "text")
        for leaf in ("after-start.md", "after-close.md", "after-learn.md"):
            text = support.read(os.path.join(folder, leaf))
            self.assertIn("Leave out", text, leaf)
            asked = "\n".join(line for line in text.split("\n") if line.startswith("- "))
            self.assertIsNone(HIDDEN.search(asked), "%s: %s" % (leaf, HIDDEN.search(asked)))


class Upgrade(unittest.TestCase):
    def engine(self, root, folder, *arguments):
        found = subprocess.run([sys.executable, os.path.join(root, "vesta", folder)] + list(arguments), capture_output=True, text=True)
        return found.returncode, found.stdout, found.stderr

    def next_engine(self, root, version, texts):
        """A newer copy of the engine in vesta/.engine.next, shipping changed text for some files."""
        target = os.path.join(root, "vesta", ".engine.next")
        shutil.copytree(BUILT, target)
        for relative, text in texts.items():
            support.write(os.path.join(target, "templates", "vesta", *relative.split("/")), text)
        listed = shipping.Shipped(target).fingerprints()
        support.write(os.path.join(target, "templates", "shipped.json"), json.dumps(listed, indent=1, sort_keys=True) + "\n")
        path = os.path.join(target, "kernel", "version.py")
        support.write(path, support.read(path).replace('ENGINE = "0.3.0"', 'ENGINE = "%s"' % version))
        self.relist(target)

    def relist(self, target):
        """Write the engine's own file list again, as the build does after a change."""
        support.write(os.path.join(target, shipping.CODE), shipping.listing(shipping.Shipped(target).code()))

    def test_an_upgrade_replaces_what_the_project_left_alone_and_keeps_what_it_changed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = os.path.join(os.path.realpath(temp), "my project")
            shutil.copytree(BUILT, os.path.join(root, "vesta", ".engine"))
            self.assertEqual(self.engine(root, ".engine", "init")[0], 0)
            read = lambda relative: support.read(os.path.join(root, "vesta", *relative.split("/")))
            mine = read("README.md") + "\nA line this project added.\n"
            support.write(os.path.join(root, "vesta", "README.md"), mine)
            config = read("vesta.yml")
            self.next_engine(root, "0.4.0", {
                "README.md": read("README.md").replace("A line this project added.\n", "") + "\nA line the new version ships.\n",
                "language.md": read("language.md") + "\nA rule the new version ships.\n",
                "walks/NEWS.md": "# News\n",
            })
            self.assertEqual(self.engine(root, ".engine", "upgrade")[0], 2)
            code, out, err = self.engine(root, ".engine.next", "upgrade")
            self.assertEqual(code, 0, out + err)
            self.assertEqual(read("README.md"), mine)
            self.assertIn("A line the new version ships.", read("README.md.new"))
            self.assertIn("- vesta/README.md (new text: vesta/README.md.new)", out)
            self.assertIn("A rule the new version ships.", read("language.md"))
            self.assertIn("vesta/language.md", out.split("\n")[1])
            self.assertEqual(read("walks/NEWS.md"), "# News\n")
            self.assertEqual(read("vesta.yml"), config)
            self.assertFalse(os.path.exists(os.path.join(root, "vesta", "vesta.yml.new")))
            self.assertEqual(sorted(name for name in os.listdir(os.path.join(root, "vesta")) if name.startswith(".engine")), [".engine"])
            self.assertEqual(self.engine(root, ".engine", "version")[1].split("\n")[0], "engine 0.4.0")
            manifest = json.loads(read(".manifest.json"))
            self.assertEqual(manifest["language.md"], shipping.digest(read("language.md")))
            self.assertNotEqual(manifest["README.md"], shipping.digest(mine))
            code, out, err = self.engine(root, ".engine", "check")
            self.assertEqual(code, 0, out + err)
            self.assertNotIn("Note:", out)
            self.assertIn("· upgrade · engine 0.3.0 to 0.4.0 · schema 1 to 1 · 2 files replaced", read("log/admissions.md"))
            # A second upgrade to the same text changes nothing more.
            self.next_engine(root, "0.4.0", {"README.md": read("README.md.new"), "language.md": read("language.md"), "walks/NEWS.md": "# News\n"})
            code, out, err = self.engine(root, ".engine.next", "upgrade")
            self.assertEqual(code, 0, out + err)
            self.assertIn("- vesta/README.md (new text: vesta/README.md.new)", out)  # still waiting to be merged
            self.assertEqual(len([line for line in read("log/admissions.md").split("\n") if "· upgrade ·" in line]), 2)
            # An engine older than the one in place refuses, and stays out of its way.
            before = fixtures_files(root)
            shutil.copytree(BUILT, os.path.join(root, "vesta", ".engine.next"))
            code, out, _ = self.engine(root, ".engine.next", "upgrade")
            self.assertEqual(code, 3)
            self.assertIn("the engine in place is 0.4.0 and this one is 0.3.0", out)
            shutil.rmtree(os.path.join(root, "vesta", ".engine.next"))
            self.assertEqual(fixtures_files(root), before)

    def test_migrations_run_in_order_and_a_missing_step_is_named(self):
        from cli import manifest
        self.assertEqual(manifest.migrations(1, 1), [])
        with self.assertRaises(LookupError) as raised:
            manifest.migrations(1, 2)
        self.assertIn("no migration from schema 1 to schema 2", str(raised.exception))
        for number in (1, 2):
            module = types.ModuleType(manifest.MIGRATION % (number, number + 1))
            module.migrate = lambda tree, number=number: number
            sys.modules[module.__name__] = module
        try:
            self.assertEqual([migrate(None) for migrate in manifest.migrations(1, 3)], [1, 2])
        finally:
            for number in (1, 2):
                del sys.modules[manifest.MIGRATION % (number, number + 1)]


class UpgradeAfterTheReview(Upgrade):
    """What the eighth review found: each case feeds the input that would make the rule false."""

    def project(self, temp, pointer=False):
        root = os.path.join(os.path.realpath(temp), "my project")
        shutil.copytree(BUILT, os.path.join(root, "vesta", ".engine"))
        self.assertEqual(self.engine(root, ".engine", "init")[0], 0)
        if pointer:
            support.write(os.path.join(root, "AGENTS.md"), support.read(os.path.join(BUILT, "templates", "pointer-block.md")))
            self.assertEqual(self.engine(root, ".engine", "init", "--pointer-file", "AGENTS.md")[0], 0)
        return root

    def read(self, root, relative):
        return support.read(os.path.join(root, "vesta", *relative.split("/")))

    def put(self, root, relative, text):
        support.write(os.path.join(root, "vesta", *relative.split("/")), text)

    def clean(self, root):
        code, out, err = self.engine(root, ".engine", "check")
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("Note:", out)

    def refused(self, root, code, said):
        """Run the upgrade and see it stop with that code and message, having changed nothing."""
        before = fixtures_files(root)
        found, out, err = self.engine(root, ".engine.next", "upgrade")
        self.assertEqual(found, code, out + err)
        self.assertIn(said, " ".join((out + err).split()))
        self.assertNotIn("Traceback", out + err)
        self.assertNotIn("did not expect", out + err)
        self.assertEqual(fixtures_files(root), before)
        self.assertIn("engine 0.3.0", self.engine(root, ".engine", "version")[1].split("\n"))

    def test_a_copy_that_stopped_half_way_is_not_put_in_place(self):
        for lost in ("steps/recall.py", "cli/commands/apply.py", "steps/text/recall.md", "files.json", "session/__init__.py"):
            with tempfile.TemporaryDirectory() as temp:
                root = self.project(temp)
                self.next_engine(root, "0.4.0", {})
                os.remove(os.path.join(root, "vesta", ".engine.next", *lost.split("/")))
                self.refused(root, 2, "this copy of the engine is not whole")
                self.clean(root)

    def test_a_stop_between_the_two_renames_is_finished_by_running_it_again(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.project(temp)
            self.put(root, "README.md", self.read(root, "README.md") + "\nMine.\n")
            self.next_engine(root, "0.4.0", {"README.md": "# New\n", "language.md": self.read(root, "language.md") + "\nA new rule.\n"})
            path = os.path.join(root, "vesta", ".engine.next", "kernel", "root.py")
            whole = support.read(path)
            support.write(path, whole.replace("        _rename(current, old)\n", "        _rename(current, old)\n        os._exit(137)\n"))
            self.relist(os.path.join(root, "vesta", ".engine.next"))
            self.assertEqual(self.engine(root, ".engine.next", "upgrade")[0], 137)
            self.assertFalse(os.path.isdir(os.path.join(root, "vesta", ".engine")))
            support.write(path, whole)
            self.relist(os.path.join(root, "vesta", ".engine.next"))
            os.remove(os.path.join(root, "vesta", ".state", "command.lock"))  # a killed command's lock; it goes stale in seconds
            code, out, err = self.engine(root, ".engine.next", "upgrade")
            self.assertEqual(code, 0, out + err)
            self.assertIn("Upgraded the engine from 0.3.0 to 0.4.0.", out)
            self.assertIn("vesta/language.md", out)
            self.assertIn("- vesta/README.md (new text: vesta/README.md.new)", out)
            self.assertEqual(len([line for line in self.read(root, "log/admissions.md").split("\n") if "· upgrade ·" in line]), 1)
            self.assertEqual(sorted(name for name in os.listdir(os.path.join(root, "vesta")) if name.startswith(".engine")), [".engine"])
            self.assertFalse(os.path.exists(os.path.join(root, "vesta", ".state", "upgrade.json")))
            self.clean(root)

    def test_a_stop_after_the_engine_is_in_place_still_reports_once(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.project(temp)
            self.next_engine(root, "0.4.0", {"language.md": self.read(root, "language.md") + "\nA new rule.\n"})
            path = os.path.join(root, "vesta", ".engine.next", "cli", "commands", "upgrade.py")
            support.write(path, support.read(path).replace("    upgrading.drop(tree)\n    for line", "    os._exit(137)\n    for line"))
            self.relist(os.path.join(root, "vesta", ".engine.next"))
            self.assertEqual(self.engine(root, ".engine.next", "upgrade")[0], 137)
            code, out, _ = self.engine(root, ".engine", "check")
            self.assertEqual(code, 0, out)
            self.assertIn("Note: an upgrade finished just before this command.", out)
            self.assertIn("vesta/language.md", out)
            self.clean(root)

    def test_an_upgrade_left_unfinished_is_named_by_the_engine_in_place(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.project(temp)
            files = shipping.digest(self.read(root, ".manifest.json"))
            self.put(root, ".state/upgrade.json", json.dumps({"from": "0.3.0", "to": "0.9.0", "report": ["x"], "files": files}))
            for _ in range(2):  # it is said at every command until the upgrade is finished
                code, out, _ = self.engine(root, ".engine", "check")
                self.assertEqual(code, 0, out)
                self.assertIn("stopped before the engine itself was put in place", out)
            # A record that no longer matches the files, is older than the engine in place, or does
            # not read says nothing, and is removed.
            stale = [
                json.dumps({"from": "0.3.0", "to": "0.9.0", "report": ["x"], "files": "0" * 64}),
                json.dumps({"from": "0.0.1", "to": "0.0.9", "report": ["x"], "files": files}),
                json.dumps({"from": "0.3.0", "to": "soon", "report": ["x"], "files": files}),
                json.dumps({"to": "0.9.0"}), "[", "",
            ]
            for text in stale:
                self.put(root, ".state/upgrade.json", text)
                code, out, err = self.engine(root, ".engine", "check")
                self.assertEqual(code, 0, out + err)
                self.assertNotIn("Note:", out)
                self.assertFalse(os.path.exists(os.path.join(root, "vesta", ".state", "upgrade.json")), text)

    def migrating(self, root, body, texts=None):
        self.next_engine(root, "0.4.0", texts or {})
        target = os.path.join(root, "vesta", ".engine.next")
        for name in ("kernel/version.py", "model/config.py"):
            path = os.path.join(target, *name.split("/"))
            support.write(path, support.read(path).replace("SCHEMA = 1\n", "SCHEMA = 2\n"))
        self.assertIn("SCHEMA = 2", support.read(os.path.join(target, "kernel", "version.py")))
        support.write(os.path.join(target, "migrations", "m1_2.py"), body)
        self.relist(target)

    def test_a_migration_runs_once_and_leaves_the_folder_clean(self):
        body = (
            "def migrate(tree):\n"
            "    tree.write('vesta/language.md', tree.read('vesta/language.md') + '\\nMigrated.\\n')\n"
            "    tree.write('vesta/decisions/SCHEMA.md', tree.read('vesta/decisions/SCHEMA.md') + '\\n')\n"
        )
        with tempfile.TemporaryDirectory() as temp:
            root = self.project(temp)
            self.migrating(root, body)
            code, out, err = self.engine(root, ".engine.next", "upgrade")
            self.assertEqual(code, 0, out + err)
            self.assertIn("The folder was brought from schema 1 to schema 2.", out)
            self.assertIn("schema: 2\n", self.read(root, "vesta.yml"))
            self.assertEqual(self.engine(root, ".engine", "version")[1].split("\n")[:2], ["engine 0.4.0", "schema 2"])
            self.clean(root)
            self.assertIn("· schema 1 to 2 ·", self.read(root, "log/admissions.md"))
            # The same engine again: the folder is at its schema, so the migration does not run twice.
            self.migrating(root, body)
            code, out, err = self.engine(root, ".engine.next", "upgrade")
            self.assertEqual(code, 0, out + err)
            self.assertEqual(self.read(root, "language.md").count("Migrated."), 1)
            self.clean(root)

    def test_a_migration_that_would_break_the_folder_changes_nothing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.project(temp)
            self.migrating(root, "def migrate(tree):\n    tree.write('vesta/decisions/SCHEMA.md', 'no schema here\\n')\n")
            self.refused(root, 3, "would leave the project with 2 errors it does not have now")
        with tempfile.TemporaryDirectory() as temp:
            root = self.project(temp)
            self.migrating(root, "import no_such_module\n\ndef migrate(tree):\n    pass\n")
            before = fixtures_files(root)
            code, out, err = self.engine(root, ".engine.next", "upgrade")
            self.assertEqual(code, 2, out + err)
            self.assertIn("no_such_module", err)
            self.assertNotIn("no migration from", err)
            self.assertEqual(fixtures_files(root), before)
        with tempfile.TemporaryDirectory() as temp:
            root = self.project(temp)
            self.migrating(root, "def migrate(tree):\n    tree.write('vesta/language.md', 'half')\n    raise RuntimeError('boom')\n")
            self.refused(root, 2, "the migration from schema 1 to schema 2 stopped (RuntimeError: boom). Remove vesta/.engine.next. Nothing was changed.")

    def test_a_hand_edit_made_before_a_migration_is_still_seen_after_it(self):
        body = "def migrate(tree):\n    tree.write('vesta/language.md', tree.read('vesta/language.md') + '\\nMigrated.\\n')\n"
        with tempfile.TemporaryDirectory() as temp:
            root = self.project(temp)
            self.put(root, "language.md", self.read(root, "language.md") + "\nA line the owner wrote.\n")
            self.migrating(root, body)
            self.refused(root, 3, "vesta/language.md was changed by hand since the engine in place last ran")
            # Any command of the engine in place logs the edit; `refused` ran one.
            code, out, err = self.engine(root, ".engine.next", "upgrade")
            self.assertEqual(code, 0, out + err)
            self.assertIn("· edit · vesta/language.md", self.read(root, "log/admissions.md"))
            self.assertIn("A line the owner wrote.\n\nMigrated.", self.read(root, "language.md"))
            self.clean(root)

    def test_a_folder_that_does_not_say_its_schema_is_not_upgraded(self):
        for line in ("", "schema: two", "schema: 0", "schema: true"):
            with tempfile.TemporaryDirectory() as temp:
                root = self.project(temp)
                self.put(root, "vesta.yml", self.read(root, "vesta.yml").replace("schema: 1\n", line + "\n" if line else ""))
                self.assertEqual(self.engine(root, ".engine", "adopt", "vesta/vesta.yml")[0], 0)
                self.next_engine(root, "0.4.0", {})
                self.refused(root, 2, "does not say which schema the folder is at")

    def test_an_upgrade_waits_for_a_hand_edit_to_be_accepted_and_for_the_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.project(temp)
            self.next_engine(root, "0.4.0", {"language.md": "# New\n"})
            self.put(root, ".state/command.lock", "")
            self.refused(root, 2, "another command is changing vesta/")
            os.remove(os.path.join(root, "vesta", ".state", "command.lock"))
            for path in ("vesta.yml", "decisions/SCHEMA.md"):
                whole = self.read(root, path)
                self.put(root, path, whole + "\n")
                self.refused(root, 3, "an upgrade cannot be done while vesta/%s is changed by hand and not accepted" % path)
                self.put(root, path, whole)

    @unittest.skipIf(os.name == "nt", "links need a privilege on Windows")
    def test_a_linked_engine_is_not_put_in_place(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.project(temp)
            os.symlink(BUILT, os.path.join(root, "vesta", ".engine.next"))
            self.refused(root, 3, "is a link to a folder elsewhere")
            self.assertFalse(os.path.islink(os.path.join(root, "vesta", ".engine")))

    def test_a_new_text_left_by_an_earlier_upgrade_is_never_written_over(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.project(temp)
            self.put(root, "README.md", self.read(root, "README.md") + "\nMine.\n")
            self.put(root, "README.md.new", "half merged by the owner\n")
            self.next_engine(root, "0.4.0", {"README.md": "# Newer\n"})
            self.refused(root, 3, "an earlier upgrade left vesta/README.md.new")

    def test_a_lost_record_of_the_shipped_files_is_said_and_nothing_is_replaced_blind(self):
        for text in (None, "[]", "{"):
            with tempfile.TemporaryDirectory() as temp:
                root = self.project(temp)
                if text is None:
                    os.remove(os.path.join(root, "vesta", ".manifest.json"))
                else:
                    self.put(root, ".manifest.json", text)
                self.assertIn("vesta/.manifest.json", self.engine(root, ".engine", "doctor")[1])
                old = self.read(root, "language.md")
                self.next_engine(root, "0.4.0", {"language.md": old + "\nA new rule.\n"})
                code, out, err = self.engine(root, ".engine.next", "upgrade")
                self.assertEqual(code, 0, out + err)
                self.assertIn("vesta/.manifest.json was missing or did not read", out)
                self.assertEqual(self.read(root, "language.md"), old)
                self.assertIn("A new rule.", self.read(root, "language.md.new"))
                self.clean(root)

    def test_the_report_names_the_block_new_settings_and_what_it_never_replaces(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.project(temp, pointer=True)
            config, log = self.read(root, "vesta.yml"), self.read(root, "log/admissions.md")
            self.next_engine(root, "0.4.0", {"vesta.yml": config + "future:\n  setting: 1\n", "log/admissions.md": "# A new heading\n"})
            target = os.path.join(root, "vesta", ".engine.next")
            block = support.read(os.path.join(target, "templates", "pointer-block.md"))
            support.write(os.path.join(target, "templates", "pointer-block.md"), block.replace("<!-- vesta:end -->", "One line more.\n<!-- vesta:end -->"))
            support.write(os.path.join(target, "templates", "shipped.json"), shipping.listing(shipping.Shipped(target).fingerprints()))
            code, out, err = self.engine(root, ".engine.next", "upgrade")
            self.assertEqual(code, 0, out + err)
            self.assertIn("The Vesta block in AGENTS.md is the earlier version's", out)
            self.assertIn("vesta/vesta.yml holds this project's own settings; it was left as it is.", out)
            self.assertIn("until the project sets it through a `config` proposal: future.", out)
            self.assertEqual(self.read(root, "vesta.yml"), config)
            self.assertEqual(self.read(root, "log/admissions.md").split("- ")[0], log.split("- ")[0])
            self.assertEqual([name for name in os.listdir(os.path.join(root, "vesta", "log")) if name.endswith(".new")], [])
            self.assertFalse(os.path.exists(os.path.join(root, "vesta", "vesta.yml.new")))

    def test_the_setup_answers_can_still_be_given_after_an_upgrade(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.project(temp)
            self.next_engine(root, "0.4.0", {})
            self.assertEqual(self.engine(root, ".engine.next", "upgrade")[0], 0)
            code, out, err = self.engine(root, ".engine", "init", "--engagement", "quiet")
            self.assertEqual(code, 0, out + err)
            self.clean(root)

    def restore(self, root, files):
        """Put the folder back as a snapshot had it, as a checkout would: working state and the new engine stay."""
        for path in fixtures_files(root):
            if path not in files and "/.state/" not in path.replace(os.sep, "/") and "/.engine.next/" not in path.replace(os.sep, "/"):
                os.remove(os.path.join(root, path))
        for path, text in files.items():
            if "/.state/" not in path.replace(os.sep, "/") and "/.engine.next/" not in path.replace(os.sep, "/"):
                support.write(os.path.join(root, path), text)

    def test_a_record_whose_files_were_put_back_is_not_trusted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.project(temp)
            before = fixtures_files(root)
            self.next_engine(root, "0.4.0", {"language.md": self.read(root, "language.md") + "\nA new rule.\n", "walks/NEWS.md": "# News\n"})
            path = os.path.join(root, "vesta", ".engine.next", "cli", "commands", "upgrade.py")
            whole = support.read(path)
            support.write(path, whole.replace("    try:\n        roots.swap(root)\n", "    os._exit(137)\n    try:\n        roots.swap(root)\n"))
            self.relist(os.path.join(root, "vesta", ".engine.next"))
            self.assertEqual(self.engine(root, ".engine.next", "upgrade")[0], 137)
            self.assertIn("A new rule.", self.read(root, "language.md"))
            self.assertTrue(os.path.exists(os.path.join(root, "vesta", ".state", "upgrade.json")))
            self.restore(root, before)
            self.assertNotIn("A new rule.", self.read(root, "language.md"))
            support.write(path, whole)
            self.relist(os.path.join(root, "vesta", ".engine.next"))
            os.remove(os.path.join(root, "vesta", ".state", "command.lock"))
            code, out, err = self.engine(root, ".engine.next", "upgrade")
            self.assertEqual(code, 0, out + err)
            self.assertIn("A new rule.", self.read(root, "language.md"))
            self.assertEqual(self.read(root, "walks/NEWS.md"), "# News\n")
            self.assertEqual(len([line for line in self.read(root, "log/admissions.md").split("\n") if "· upgrade ·" in line]), 1)
            self.clean(root)

    def test_files_brought_to_a_newer_version_are_not_taken_back(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.project(temp)
            self.next_engine(root, "0.4.0", {})
            files = shipping.digest(self.read(root, ".manifest.json"))
            self.put(root, ".state/upgrade.json", json.dumps({"from": "0.3.0", "to": "0.5.0", "report": ["x"], "files": files}))
            self.refused(root, 3, "an upgrade to engine 0.5.0 already brought the files under vesta/ up to date, and this engine is 0.4.0")

    def test_a_lost_record_of_approvals_stops_the_upgrade(self):
        for text in (None, "[]", "{"):
            with tempfile.TemporaryDirectory() as temp:
                root = self.project(temp)
                if text is None:
                    os.remove(os.path.join(root, "vesta", "log", "admitted.json"))
                else:
                    self.put(root, "log/admitted.json", text)
                self.next_engine(root, "0.4.0", {"language.md": "# New\n"})
                before = fixtures_files(root)
                code, out, err = self.engine(root, ".engine.next", "upgrade")
                self.assertEqual(code, 3, out + err)
                self.assertIn("vesta/log/admitted.json is missing or does not read", out)
                self.assertEqual(fixtures_files(root), before)

    def test_a_schema_file_never_recorded_stops_the_upgrade(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.project(temp)
            self.put(root, "glossary/SCHEMA.md", "# Glossary\n")
            self.next_engine(root, "0.4.0", {})
            self.refused(root, 3, "an upgrade cannot be done while vesta/glossary/SCHEMA.md is changed by hand and not accepted")

    def test_a_copy_with_files_that_were_not_shipped_or_cut_short_is_not_put_in_place(self):
        for extra in ("extra.py", "junk/a.txt", "templates/vesta/EXTRA.md", "templates/other.md"):
            with tempfile.TemporaryDirectory() as temp:
                root = self.project(temp)
                self.next_engine(root, "0.4.0", {})
                support.write(os.path.join(root, "vesta", ".engine.next", *extra.split("/")), "left by an older copy\n")
                self.refused(root, 2, "%s is not a file that was shipped" % extra)
        for cut in ("kernel/shipped.py", "cli/main.py", "cli/commands/upgrade.py", "kernel/tree.py"):
            with tempfile.TemporaryDirectory() as temp:
                root = self.project(temp)
                self.next_engine(root, "0.4.0", {})
                path = os.path.join(root, "vesta", ".engine.next", *cut.split("/"))
                support.write(path, support.read(path)[:900])
                self.refused(root, 2, "this copy of the engine is not whole")

    def test_setting_up_from_a_copy_that_is_not_whole_writes_nothing(self):
        for lost in ("steps/sweep.py", "proposals/add.py", "files.json"):
            with tempfile.TemporaryDirectory() as temp:
                root = os.path.join(os.path.realpath(temp), "my project")
                shutil.copytree(BUILT, os.path.join(root, "vesta", ".engine"))
                os.remove(os.path.join(root, "vesta", ".engine", *lost.split("/")))
                code, out, err = self.engine(root, ".engine", "init")
                self.assertEqual(code, 2, out + err)
                self.assertIn("this copy of the engine is not whole", err)
                self.assertNotIn("Traceback", err)
                self.assertEqual(os.listdir(os.path.join(root, "vesta")), [".engine"])

    def test_a_new_text_beside_a_file_that_is_now_current_is_named_for_deleting(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.project(temp)
            self.put(root, "language.md.new", "left by an earlier upgrade\n")
            self.put(root, "README.md", self.read(root, "README.md") + "\nMine.\n")
            self.put(root, "README.md.new", "half merged by the owner\n")
            self.next_engine(root, "0.4.0", {"language.md": self.read(root, "language.md") + "\nA new rule.\n"})
            code, out, err = self.engine(root, ".engine.next", "upgrade")
            self.assertEqual(code, 0, out + err)
            self.assertIn("for the owner to delete: vesta/language.md.new", out)
            self.assertIn("- vesta/README.md (new text: vesta/README.md.new)", out)
            self.assertNotIn("Left for the owner to merge: none", out)
            self.assertEqual(self.read(root, "README.md.new"), "half merged by the owner\n")

    def test_a_long_change_keeps_its_locks_from_going_stale(self):
        from kernel import tree as trees
        with tempfile.TemporaryDirectory() as temp:
            disk = trees.DiskTree(temp)
            for lock in (trees.COMMIT_LOCK, trees.COMMAND_LOCK):
                support.write(disk.locate(lock), "")
                os.utime(disk.locate(lock), (1, 1))
            overlay = trees.Overlay(disk)
            overlay.write("vesta/a.md", "a\n")
            overlay._commit(overlay.changed())
            for lock in (trees.COMMIT_LOCK, trees.COMMAND_LOCK):
                self.assertGreater(os.path.getmtime(disk.locate(lock)), 1000)
            disk.keep("vesta/.state/absent.lock")

    def test_every_rule_an_upgrade_cites_is_in_the_shipped_file(self):
        text = support.read(os.path.join(BUILT, "templates", "vesta", "INTERNALS.md"))
        section_text = " ".join(text.split("## Upgrades\n")[1].split("\n## ")[0].split())
        for said in ("never goes back", "is never written over", "a link to a folder elsewhere", "holds one that was not shipped",
                     "changed by hand and not accepted", "not logged yet", "without a proposal", "running it again"):
            self.assertIn(said, section_text)


def fixtures_files(root):
    found = {}
    for folder, names, leaves in os.walk(os.path.join(root, "vesta")):
        names[:] = [name for name in names if name != "__pycache__"]
        for leaf in leaves:
            if not leaf.endswith(".pyc"):
                found[os.path.relpath(os.path.join(folder, leaf), root)] = support.read(os.path.join(folder, leaf))
    return found


class Documents(unittest.TestCase):
    def test_the_product_readme_says_what_a_person_needs_to_decide(self):
        text = " ".join(support.read(os.path.join(support.REPO, "README.md")).split())
        for said in ("/vesta-hook", "/vesta-insight", "/vesta-learn", "/vesta-init", ".claude/skills", "Python 3.9", "quiet", "standard", "active",
                     "What a session costs", "What it does not do", "experimental", "upgrade"):
            self.assertIn(said, text)
        self.assertIsNone(re.search(r"\b(latch|ladder|sweep|bundle)\b", text, re.I))

    def test_the_init_skill_carries_the_upgrade(self):
        text = " ".join(support.read(os.path.join(support.REPO, "skills", "vesta-init", "SKILL.md")).split())
        for said in ("vesta/.engine.next", "upgrade", ".new"):
            self.assertIn(said, text)
        self.assertTrue(len(support.read(os.path.join(support.REPO, "skills", "vesta-init", "SKILL.md")).split("\n")) <= 120)


if __name__ == "__main__":
    unittest.main()
