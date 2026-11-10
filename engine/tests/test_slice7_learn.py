import io
import json
import os
import re
import unittest

import support
import fixtures
from fixtures import BODY, Project, decision
from cli import manifest
from kernel import yamlsubset
from session import passes
from test_slice4_sessions import GOLDEN, five, tokens
from test_slice5_close import LABEL, add, item, notes
from test_slice6_proposals import OWNER, apply, front, propose

TITLE = "Every figure is checked on the day it is sent"
STATE = "vesta/.state/pass.json"


def draft_of(title, when):
    return front(decision("NEW", "NEW", decided="", approved_by="", when=when)) + BODY.replace(TITLE, title)


def shipped():
    """The shipped configuration, whole, reading changes by file times so a test needs no git."""
    config = yamlsubset.read(support.read(os.path.join(fixtures.TEMPLATES, "vesta.yml")))
    config["adapters"]["changes"] = "mtime"
    return config


def session(project, *items):
    """One closed session that wrote those notes. Returns their labels."""
    code, out, err = add(project, *items)
    assert code == 0, out + err
    project.run("session", "close")
    project.clock.advance(seconds=60)
    return LABEL.findall(out)


def learn(project, *arguments):
    code, out, err = project.run("walk", "learn", *arguments)
    assert code == 0, out + err
    return out


def section(sheet, title):
    """The text of one section of a sheet, below its heading."""
    parts = re.split(r"^## \d+\. ", sheet, flags=re.M)
    return parts[[part.split("\n")[0] for part in parts].index(title)].split("\n", 1)[1]


def seal(project, *arguments, **options):
    return project.run("pass", "seal", *arguments, stdin=io.StringIO(options.get("note", "")))


def fields_of(project, path):
    return yamlsubset.read(project.read(path).split("\n---\n")[0][4:] + "\n")


def distinct(project):
    """Three decisions no two of which are alike."""
    project.put(decision("D-001", "0000000a", when="calling an outside service"))
    project.put(decision("D-002", "0000000b", when="writing the user guide"), body=BODY.replace(TITLE, "Guides name their reader first"))
    project.put(decision("D-003", "0000000c", when="naming a release"), body=BODY.replace(TITLE, "Releases carry a plain number"))


class Window(unittest.TestCase):
    def test_a_pass_freezes_its_window_and_a_second_walk_resumes_it(self):
        with Project(init=True, config=shipped()) as project:
            first = session(project, item(), item(title="A second thing"))
            out = learn(project)
            self.assertIn("This pass was opened now. It reads the 2 notes open", out)
            self.assertIn("Pass: pass-001", out)
            state = json.loads(project.read(STATE))
            self.assertEqual((state["number"], len(state["window"])), (1, 2))
            later = session(project, item(title="Written after the pass opened"))
            again = learn(project)
            self.assertIn("This pass was already open", again)
            self.assertEqual(json.loads(project.read(STATE))["window"], state["window"])
            window = section(again, "Window")
            for label in first:
                self.assertIn(label, window)
            self.assertNotIn(later[0], again)
            self.assertNotIn("Written after the pass opened", again)
            self.assertIn("`walk learn --from gate`", again)
            self.assertNotIn("--session", again.split("---\n")[-1])
            self.assertEqual(project.run("walk", "learn", "--session", "S-20260105-0000")[0], 2)

    def test_the_window_prints_every_open_note_the_sessions_the_read_titles_and_the_rejections(self):
        with Project(init=True, config=shipped()) as project:
            distinct(project)
            old = session(project, item(title="Read and filed by the first pass"))
            learn(project)
            self.assertEqual(seal(project)[0], 0)
            evidence = session(project, item(title="The owner chose plain numbers", via="owner-steer", steer_kind="choice", moment="start", missed_by="none"))
            label = propose(project, "add", "decisions", draft=draft_of(title="Letters go out under the owner's name", when="sending a letter"), evidence=evidence)
            self.assertEqual(project.run("reject", label, "--by", OWNER, "--reason", "not worth a rule")[0], 0)
            one = session(project, item(title="Seen in the first session", recheck="exists src/later.py"))
            two = session(project, item(title="Seen in the second session", body="A body of its own."))
            project.write("src/later.py", "x\n")
            out = learn(project)
            window = section(out, "Window")
            self.assertIn("pass-002 reads 2 notes, from 2 sessions.", window)
            for label_, title in ((one[0], "Seen in the first session"), (two[0], "Seen in the second session")):
                self.assertIn("%s · date: " % label_, window)
                self.assertIn("  " + title, window)
            self.assertIn("    A body of its own.", window)
            self.assertIn("Notes whose `recheck` fires now: %s" % one[0], window)
            self.assertIn("- %s · off-map · Read and filed by the first pass" % old[0], window)
            self.assertIn("· rejected by %s — not worth a rule" % OWNER, window)
            self.assertNotIn("The owner chose plain numbers", window)
            self.assertIn("Trigger review: never run; passes sealed so far: 1.", window)

    def test_a_later_part_without_an_open_pass_is_refused(self):
        with Project(init=True, config=shipped()) as project:
            code, out, _ = project.run("walk", "learn", "--from", "gate")
            self.assertEqual(code, 3)
            self.assertIn("no pass is open", out)
            self.assertIn("vesta/INTERNALS.md, Learn passes", out)
            self.assertFalse(os.path.isfile(project.path(STATE)))
            self.assertIn("## Learn passes", project.read("vesta/INTERNALS.md"))


class Steps(unittest.TestCase):
    def test_counts_prints_each_figure_alone_and_no_combined_one(self):
        with Project(init=True, config=shipped()) as project:
            five(project)
            project.run("walk", "start", "--ask", "raise the timeout", "--paths", "src/http/client.py")
            project.run("load", "D-003", "--by", "index")
            project.run("mark", "D-001=applied", "D-004=not-applicable")
            session(project, item(via="lens:friction"), item(title="Twenty was wanted", via="owner-steer", steer_kind="correction", moment="start", missed_by="D-004"))
            project.run("walk", "start", "--ask", "another", "--paths", "src/http/client.py")
            project.run("session", "close")
            counts = section(learn(project), "Counts").split("**Do:**")[0]
            self.assertIn("- D-001 · read by: scope 2, index 0, trigger 0, sweep 0 · marked: applied 1, not-applicable 0, should-have-loaded 0, unmarked 1, unclosed 0", counts)
            self.assertIn("- D-003 · read by: scope 0, index 1, trigger 0, sweep 0 · marked: applied 0, not-applicable 0, should-have-loaded 0, unmarked 1, unclosed 0", counts)
            self.assertIn("- D-004 · read by: scope 2, index 0, trigger 0, sweep 0 · marked: applied 0, not-applicable 1,", counts)
            self.assertIn("- read by no session: D-002", counts)
            self.assertIn("- lens:friction: 1", counts)
            self.assertIn("- owner-steer: 1", counts)
            self.assertIn("- D-004: 1", counts)
            self.assertNotIn("%", counts)
            self.assertNotIn("/ ", counts)
            self.assertIsNone(re.search(r"\b(rank|score|rate|ratio)", counts, re.I))

    def test_counts_start_at_the_opening_of_the_last_pass(self):
        with Project(init=True, config=shipped()) as project:
            five(project)
            project.run("walk", "start", "--ask", "one", "--paths", "src/http/client.py")
            project.run("session", "close")
            project.clock.advance(seconds=60)
            learn(project)
            seal(project)
            project.clock.advance(seconds=60)
            project.run("walk", "start", "--ask", "two", "--paths", "docs/guide.md")
            project.run("session", "close")
            counts = section(learn(project), "Counts")
            self.assertIn("after pass-001 opened", counts)
            self.assertIn("- D-002 · read by: scope 1,", counts)
            self.assertIn("- read by no session: D-001, D-003, D-004", counts)

    def test_the_trigger_review_prints_only_where_asked_for(self):
        with Project(init=True, config=shipped()) as project:
            five(project)
            out = learn(project)
            self.assertNotIn(". Trigger review\n", out)
            self.assertNotIn("- D-001: False if:", out)
            asked = learn(project, "--with", "trigger-review")
            review = section(asked, "Trigger review")
            self.assertIn("- **D-003/t1**, probe: fired", review)
            self.assertIn("- D-001: False if: the source is frozen before drafting starts.", review)
            self.assertNotIn("D-005", review)
            code, out, _ = seal(project)
            self.assertIn("- Trigger review: run — 2 live, 1 fired (D-003/t1)", out)
            self.assertIn("Trigger review: last run in pass-001; passes sealed since: 0.", learn(project))
            # Asking for it on a later part prints nothing of it, so nothing is recorded as run.
            learn(project, "--from", "gate", "--with", "trigger-review")
            self.assertIn("- Trigger review: not run", seal(project)[1])

    def test_route_prints_the_bars_and_the_ladder_as_the_walk_file_holds_them(self):
        with Project(init=True, config=shipped()) as project:
            out = learn(project)
            walk = project.read("vesta/walks/learn.md")
            for name, following in (("Shapes", "## Bars"), ("Bars", "## Ladder"), ("Ladder", None)):
                text = walk.split("## %s\n" % name)[1]
                text = (text.split(following)[0] if following else text).strip("\n")
                self.assertIn(text, out)

    def test_consolidate_prints_a_planted_pair_in_full_and_none_without_one(self):
        with Project(init=True, config=shipped()) as project:
            distinct(project)
            self.assertEqual(section(learn(project), "Consolidate").split("**Do:**")[0].strip(), "none")
            seal(project)
            project.put(decision("D-004", "0000000d", when="calling an outside service"), body=BODY.replace(TITLE, "Calling an outside service is checked"))
            consolidate = section(learn(project), "Consolidate")
            self.assertIn("Pair 1: D-001 and D-004", consolidate)
            for label in ("D-001", "D-004"):
                self.assertIn("---- %s, in full (vesta/decisions/%s.md) ----" % (label, label), consolidate)
            self.assertIn("# Calling an outside service is checked", consolidate)
            self.assertNotIn("D-002", consolidate)
            self.assertIn("- Consolidation: 1 pair found, merged by nothing yet", seal(project, "--note", "-", note="Consolidation: merged by nothing yet\n")[1])

    def test_the_gate_prints_every_waiting_proposal_with_its_case(self):
        with Project(init=True, config=shipped()) as project:
            distinct(project)
            evidence = session(project, item(title="The owner chose plain numbers", via="owner-steer", steer_kind="choice", moment="start", missed_by="none"))
            learn(project)
            label = propose(project, "add", "decisions", draft=draft_of(title="Letters go out under the owner's name", when="sending a letter"), evidence=evidence)
            gate = section(learn(project, "--from", "gate"), "Gate")
            self.assertIn("- %s · add decisions · Change one thing" % label, gate)
            self.assertIn("  evidence: 1 note · sessions they come from: 1 ·", gate)
            self.assertIn("  Why:\n    It keeps going wrong.", gate)
            self.assertIn("  Counter-case:\n    It may reach too far.", gate)
            self.assertIn("`walk learn --from seal`", learn(project, "--from", "gate"))

    def test_a_capture_source_added_to_the_manifest_reaches_the_steers_step(self):
        config = shipped()
        config["adapters"]["capture"] = ["jot", "spoken"]
        manifest.CAPTURE["spoken"] = "capture_spoken"
        try:
            with Project(init=True, config=config) as project:
                self.assertEqual(project.check(), [])
                project.run("jot", "--steer", "-", stdin=io.StringIO("twenty seconds, not thirty"))
                _, out, _ = project.run("walk", "close")
                steers = out.split("Steers\n")[-1]
                self.assertIn("twenty seconds, not thirty (from jot)", steers)
                self.assertIn("said aloud: keep the old name (from spoken)", steers)
        finally:
            del manifest.CAPTURE["spoken"]


class Seal(unittest.TestCase):
    def test_the_seal_archives_holds_and_writes_the_note(self):
        with Project(init=True, config=shipped()) as project:
            distinct(project)
            plain = session(project, item(title="Read and done with"), item(title="Noise from a test run"))
            kept = session(project, item(title="Waits for a second session"))
            cited = session(project, item(title="The owner chose plain numbers", via="owner-steer", steer_kind="choice", moment="start", missed_by="none"))
            learn(project)
            code, out, _ = project.run("obs", "dispose", plain[1], "--as", "dropped - a test run, not the work")
            self.assertEqual(code, 0, out)
            dropped = "vesta/observations/archive/pass-001/%s.md" % plain[1]
            self.assertEqual(fields_of(project, dropped)["disposition"], "dropped — a test run, not the work")
            label = propose(project, "add", "decisions", draft=draft_of(title="Letters go out under the owner's name", when="sending a letter"), evidence=cited)
            sheet = section(learn(project, "--from", "seal"), "Seal")
            self.assertIn("- %s · The owner chose plain numbers · evidence of %s, which waits for the owner · kept open by 0 earlier passes · at the seal: kept open" % (cited[0], label), sheet)
            self.assertIn("- %s · Read and done with · cited by no waiting proposal" % plain[0], sheet)
            self.assertNotIn(plain[1], sheet)
            code, out, _ = seal(project, "--hold", kept[0], "--note", "-", note="Groups: 1\nUngrouped: 2\nNot done: the trigger review\nWaiting %s: a second session\n" % kept[0])
            self.assertEqual(code, 0, out)
            self.assertEqual(fields_of(project, "vesta/observations/archive/pass-001/%s.md" % plain[0])["disposition"], "read (pass-001)")
            for name in (kept[0], cited[0]):
                held = fields_of(project, "vesta/observations/open/%s.md" % name)
                self.assertEqual((held["disposition"], held["held"]), ("open", ["pass-001"]))
            self.assertFalse(os.path.isfile(project.path(STATE)))
            note = project.read("vesta/log/passes/pass-001.md")
            self.assertEqual([line for line in note.split("\n")[:9] if not line.startswith("- Held")], [
                "# Pass 001 — 2026-01-05",
                "",
                "- Window: 4 observations from 3 sessions",
                "- Groups: 1 · Ungrouped: 2 · Dropped as noise: 1",
                "- Proposals: %s add decisions pending" % label,
                "- Trigger review: not run",
                "- Consolidation: no pair found",
                "- Not done: the trigger review",
            ])
            for said in ("%s (a second session)" % kept[0], "%s (%s is waiting for the owner)" % (cited[0], label)):
                self.assertIn(said, note.split("\n")[5])
            self.assertIn(note, out)
            self.assertEqual(project.check(), [])
            # The next pass has the next number, reads the two held notes, and reports what became of the proposal.
            self.assertEqual(apply(project, label)[0], 0)
            out = learn(project)
            self.assertIn("pass-002 reads 1 note, from 1 session.", out)
            code, out, _ = seal(project)
            self.assertIn("- Proposals: none", out)
            self.assertEqual(fields_of(project, "vesta/observations/archive/pass-002/%s.md" % kept[0])["held"], ["pass-001"])
            self.assertEqual(project.check(), [])

    def test_a_proposal_decided_in_the_pass_is_named_with_what_became_of_it(self):
        with Project(init=True, config=shipped()) as project:
            distinct(project)
            one = session(project, item(title="The owner chose plain numbers", via="owner-steer", steer_kind="choice", moment="start", missed_by="none"))
            two = session(project, item(title="A second choice of the owner", via="owner-steer", steer_kind="choice", moment="start", missed_by="none"))
            learn(project)
            yes = propose(project, "add", "decisions", draft=draft_of(title="Letters go out under the owner's name", when="sending a letter"), evidence=one)
            no = propose(project, "add", "decisions", draft=draft_of(title="Parcels are weighed twice", when="posting a parcel"), evidence=two)
            self.assertEqual(apply(project, yes)[0], 0)
            self.assertEqual(project.run("reject", no, "--by", OWNER, "--reason", "too rare")[0], 0)
            self.assertTrue(os.path.isfile(project.path("vesta/observations/archive/pass-001/%s.md" % one[0])))
            code, out, _ = seal(project)
            self.assertIn("- Proposals: %s add → D-004 approved · %s add rejected" % (yes, no), out)
            self.assertIn("Archived as read: 0. Kept open for a later pass: 0.", out)
            self.assertEqual(project.check(), [])

    def test_a_note_held_three_times_is_archived_unless_named(self):
        with Project(init=True, config=shipped()) as project:
            distinct(project)
            cited = session(project, item(title="The owner chose plain numbers", via="owner-steer", steer_kind="choice", moment="start", missed_by="none"))
            other = session(project, item(title="Waits and waits"))
            propose(project, "add", "decisions", draft=draft_of(title="Letters go out under the owner's name", when="sending a letter"), evidence=cited)
            for number in (1, 2, 3):
                learn(project)
                self.assertEqual(seal(project, "--hold", other[0])[0], 0)
            path = "vesta/observations/open/%s.md" % cited[0]
            self.assertEqual(fields_of(project, path)["held"], ["pass-001", "pass-002", "pass-003"])
            learn(project)
            sheet = section(learn(project, "--from", "seal"), "Seal")
            self.assertIn("kept open 3 times already: archived as read unless named", sheet)
            self.assertEqual(seal(project, "--hold", other[0])[0], 0)
            self.assertEqual(fields_of(project, "vesta/observations/archive/pass-004/%s.md" % cited[0])["disposition"], "read (pass-004)")
            self.assertEqual(project.check(), [])
            # The proposal still stands on its evidence, and deciding it leaves the archived note as the pass left it.
            self.assertEqual(project.run("reject", "P-001", "--reason", "not now")[0], 0)
            self.assertEqual(fields_of(project, "vesta/observations/archive/pass-004/%s.md" % cited[0])["disposition"], "read (pass-004)")
            self.assertEqual(len(fields_of(project, "vesta/observations/open/%s.md" % other[0])["held"]), 4)

    def test_what_the_seal_and_dispose_refuse(self):
        with Project(init=True, config=shipped()) as project:
            distinct(project)
            self.assertEqual(seal(project)[0], 3)
            self.assertEqual(project.run("obs", "dispose", "O-1", "--as", "moot — gone")[0], 3)
            first = session(project, item())
            cited = session(project, item(title="The owner chose plain numbers", via="owner-steer", steer_kind="choice", moment="start", missed_by="none"))
            learn(project)
            late = session(project, item(title="After the pass opened"))
            propose(project, "add", "decisions", draft=draft_of(title="Letters go out under the owner's name", when="sending a letter"), evidence=cited)
            before = project.files("vesta")
            for arguments, code, said in (
                (("obs", "dispose", first[0], "--as", "read"), 2, "`--as` takes `dropped — <reason>` or `moot — <reason>`"),
                (("obs", "dispose", first[0]), 2, "obs dispose <id> --as"),
                (("obs", "dispose", "O-404", "--as", "moot — gone"), 2, "names no note"),
                (("obs", "dispose", late[0], "--as", "moot — gone"), 3, "written after the pass opened"),
                (("obs", "dispose", cited[0], "--as", "moot — gone"), 3, "which waits for the owner"),
                (("pass", "seal", "--hold", late[0]), 3, "not a note of this pass that is still open"),
                (("pass", "seal", "--note", "nowhere.txt"), 2, "is not a text file of this project"),
                (("pass", "open"), 2, "`pass` takes: seal"),
            ):
                got, out, err = project.run(*arguments)
                self.assertEqual(got, code, out + err)
                self.assertIn(said, out + err)
            code, out, err = seal(project, "--note", "-", note="Groups: 2\nMood: fine\n")
            self.assertEqual(code, 2)
            self.assertIn("`Mood: fine`", err)
            self.assertEqual(project.files("vesta"), before)
            self.assertEqual(project.run("obs", "dispose", first[0], "--as", "-", stdin=io.StringIO("moot: the export was removed\n"))[0], 0)
            code, out, _ = project.run("obs", "dispose", first[0], "--as", "moot — again")
            self.assertEqual(code, 3)
            self.assertIn("already dealt with: moot — the export was removed", out)
            self.assertIn("Learn pass: pass-001 is open", project.run("doctor")[1])

    def test_a_pass_state_that_does_not_read_is_named(self):
        with Project(init=True, config=shipped()) as project:
            project.write(STATE, "{")
            code, _, err = project.run("walk", "learn")
            self.assertEqual(code, 2)
            self.assertIn("vesta/.state/pass.json does not read", err)


class Reminders(unittest.TestCase):
    def config(self, **learn_):
        config = shipped()
        config["reminders"]["learn"].update((name.replace("_", "-"), value) for name, value in learn_.items())
        return config

    def notices(self, project):
        _, out, _ = project.run("walk", "start", "--ask", "something")
        project.run("session", "close")
        project.clock.advance(seconds=60)
        return section(out, "Notices").split("**Do:**")[0]

    def test_no_learn_reminder_prints_where_it_is_off(self):
        with Project(init=True, config=self.config(enabled=False, open_observations=1, sessions_since_pass=1)) as project:
            session(project, item(), item(title="Another"))
            session(project, item(title="A third"))
            self.assertNotIn("learn pass due", self.notices(project))

    def test_the_session_count_reminds_after_the_third_closed_session_and_not_before(self):
        with Project(init=True, config=self.config(open_observations=0, sessions_since_pass=3)) as project:
            self.assertNotIn("learn pass due", self.notices(project))
            self.assertNotIn("learn pass due", self.notices(project))
            self.assertNotIn("learn pass due", self.notices(project))
            due = self.notices(project)
            self.assertIn("learn pass due: 3 sessions have closed since the last learn pass", due)
            self.assertNotIn("notes are open", due)
            learn(project)
            seal(project)
            project.clock.advance(seconds=60)
            self.assertNotIn("learn pass due", self.notices(project))

    def test_an_abandoned_session_is_not_counted(self):
        with Project(init=True, config=self.config(open_observations=0, sessions_since_pass=1)) as project:
            project.run("walk", "start", "--ask", "something")
            name = re.search(r"S-[0-9]{8}-[0-9a-f]{4}", project.run("doctor")[1]).group(0)
            project.run("session", "abandon", name)
            self.assertNotIn("learn pass due", self.notices(project))
            self.assertIn("learn pass due: 1 session has closed", self.notices(project))

    def test_held_notes_are_not_counted_and_waiting_proposals_can_be_left_out(self):
        config = self.config(open_observations=2)
        config["reminders"]["pending-proposals"]["enabled"] = False
        with Project(init=True, config=config) as project:
            distinct(project)
            held = session(project, item(), item(title="Another"))
            learn(project)
            seal(project, "--hold", ",".join(held))
            label = propose(project, "add", "decisions", draft=draft_of(title="Letters go out under the owner's name", when="sending a letter"))
            found = self.notices(project)
            self.assertNotIn("learn pass due", found)
            self.assertNotIn(label, found)
            session(project, item(title="A third"), item(title="A fourth"))
            self.assertIn("learn pass due: 2 notes are open", self.notices(project))


class Sheets(unittest.TestCase):
    def test_no_other_sheet_carries_text_of_the_learn_walk(self):
        with Project(init=True, config=shipped()) as project:
            five(project)
            lines = [line.strip() for line in project.read("vesta/walks/learn.md").split("\n") if len(line.strip()) > 30]
            _, start, _ = project.run("walk", "start", "--ask", "raise the timeout", "--paths", "src/http/client.py")
            _, close, _ = project.run("walk", "close")
            name = re.search(r"S-[0-9]{8}-[0-9a-f]{4}", start).group(0)
            add(project, item())
            project.run("session", "close")
            _, second, _ = project.run("walk", "close", "--from", "choices", "--session", name)
            for sheet in (start, close, second):
                self.assertTrue(len(sheet) > 500)
                for line in lines:
                    self.assertNotIn(line, sheet)

    def test_the_three_parts_equal_the_golden_file(self):
        with Project(init=True, config=shipped()) as project:
            five(project)
            # One note a day: a note's label opens with its date, so the window's order is the same on every run.
            session(project, item(via="lens:friction"))
            project.clock.advance(days=1)
            session(project, item(title="Twenty seconds was wanted", via="owner-steer", steer_kind="correction", moment="start", missed_by="D-004"))
            project.clock.advance(days=1)
            cited = session(project, item(title="The owner chose plain numbers", via="owner-steer", steer_kind="choice", moment="start", missed_by="none"))
            first = learn(project, "--with", "trigger-review", "--ask", "why does the date come up twice?")
            propose(project, "add", "decisions", draft=draft_of(title="Letters go out under the owner's name", when="sending a letter"), evidence=cited)
            self.assertIn("`walk learn --with trigger-review --from gate`", first)
            second = learn(project, "--with", "trigger-review", "--from", "gate")
            third = learn(project, "--with", "trigger-review", "--from", "seal")
            sheet = LABEL.sub("O-TOKEN", tokens("\n=====\n\n".join((first, second, third)), project.root))
            path = os.path.join(GOLDEN, "learn-sheet.md")
            if os.environ.get("VESTA_WRITE_GOLDEN"):
                support.write(path, sheet)
            self.assertEqual(sheet, support.read(path))

    def test_the_shipped_configuration_is_whole_and_clean(self):
        with Project(init=True) as project:
            self.assertEqual(fixtures.built_config(), yamlsubset.read(support.read(os.path.join(fixtures.TEMPLATES, "vesta.yml"))))
            self.assertEqual(project.check(), [])


class LearnSkill(unittest.TestCase):
    def test_the_skill_names_only_commands_the_engine_has_and_carries_the_rules(self):
        text = " ".join(support.read(os.path.join(support.REPO, "skills", "vesta-learn", "SKILL.md")).split())
        used = set(re.findall(r"`vesta ([a-z]+)", text))
        self.assertEqual(used - set(manifest.COMMANDS), set())
        self.assertTrue({"walk", "obs", "propose", "proposals", "apply", "reject", "pass", "doctor", "version"} <= used)
        insight = " ".join(support.read(os.path.join(support.REPO, "skills", "vesta-insight", "SKILL.md")).split())
        rule = insight[insight.index("Run `apply` only for a proposal"):insight.index("by hand.", insight.index("Run `apply` only")) + len("by hand.")]
        self.assertIn(rule, " ".join(support.read(os.path.join(support.REPO, "skills", "vesta-init", "SKILL.md")).split()))
        for phrase in (rule, "walk learn", "--with trigger-review", "--ask -", "never without the owner present", "carried out honestly", "cannot tell whether the owner approved it"):
            self.assertIn(phrase, text)
        for word in ("lens", "latch", "ladder", "sweep", "bundle"):
            self.assertIsNone(re.search(r"\b%s" % word, text.split("## Procedure")[1], re.I), word)

    def test_every_step_of_the_learn_walk_has_its_own_text(self):
        folder = os.path.join(support.ENGINE, "steps", "text")
        config = yamlsubset.read(support.read(os.path.join(fixtures.TEMPLATES, "vesta.yml")))
        for step in config["checkpoints"]["learn"]["steps"]:
            self.assertTrue(os.path.isfile(os.path.join(folder, step + ".md")), step)
        self.assertEqual(passes.HOLD_LIMIT, 3)


if __name__ == "__main__":
    unittest.main()
