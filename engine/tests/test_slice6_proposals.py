import io
import json
import os
import re
import unittest

import support
import fixtures
from fixtures import BODY, Project, decision
from kernel import tree as trees
from kernel import yamlsubset
from test_slice4_sessions import five, mtime_config
from test_slice5_close import add as add_notes, item

OWNER = "A. Reviewer"
LABEL = re.compile(r"\b(P-[0-9]{3})\b")


def front(fields):
    return "---\n" + yamlsubset.write(fields) + "---\n"


def draft_of(**changes):
    fields = decision("NEW", "NEW", decided="", approved_by="", **changes)
    return front(fields) + BODY.replace("Every figure is checked on the day it is sent", changes.get("title", "Letters go out under the owner's name"))


def propose(project, kind, target, change=None, draft=None, evidence=None, title="Change one thing", source="init"):
    """Start a proposal and fill it. Returns its label."""
    arguments = ["propose", kind, "--target", target, "--source", source]
    if evidence:
        arguments += ["--evidence", ",".join(evidence)]
    code, out, err = project.run(*arguments)
    assert code == 0, out + err
    label = LABEL.search(out).group(1)
    path = "vesta/proposals/%s.md" % label
    text = project.read(path)
    head = text.split("\n---\n", 1)[0] + "\n---\n"
    scaffold = text.split("\n## Change\n", 1)[1]
    body = "# %s\n\n## Why\nIt keeps going wrong.\n\n## Counter-case\nIt may reach too far.\n\n## Change\n%s" % (title, change + "\n" if change is not None else scaffold)
    project.write(path, head + body)
    if draft is not None:
        project.write("vesta/proposals/%s.draft.md" % label, draft)
    return label


def apply(project, label, name=OWNER):
    return project.run("apply", label, "--approved-by", name)


def set_block(text):
    return "```vesta-set\n%s\n```" % text


def pair(find, replace):
    return "````find\n%s\n````\n````replace\n%s\n````" % (find, replace)


def started(config=None):
    project = Project(init=True, config=config or mtime_config())
    five(project)
    return project


def errors(project):
    return [line for line in project.check() if line.startswith("error")]


class Add(unittest.TestCase):
    def test_apply_is_the_record_of_approval_and_a_name_or_reference_is_bookkeeping(self):
        with started() as project:
            log = lambda: project.read("vesta/log/admissions.md").strip().split("\n")[-1]
            label = propose(project, "add", "decisions", draft=draft_of(when="sending a letter"))
            code, out, err = project.run("apply", label)
            self.assertEqual(code, 0, out + err)
            self.assertTrue(log().endswith("· approved · evidence 0"), log())
            self.assertIn("approved-by: the owner", project.read("vesta/decisions/D-006.md"))
            self.assertIn("outcome: approved, 2026-01-05", project.read("vesta/log/proposals/%s.md" % label))
            label = propose(project, "add", "decisions", draft=draft_of(when="posting a parcel"))
            self.assertEqual(project.run("apply", label, "--ref", "4e1f0c2")[0], 0)
            self.assertTrue(log().endswith("· approved · evidence 0 · ref 4e1f0c2"), log())
            self.assertIn("approved-by: 4e1f0c2", project.read("vesta/decisions/D-007.md"))
            label = propose(project, "add", "decisions", draft=draft_of(when="paying an invoice"))
            self.assertEqual(project.run("apply", label, "--approved-by", OWNER, "--ref", "4e1f0c2")[0], 0)
            self.assertTrue(log().endswith("· approved by %s · evidence 0 · ref 4e1f0c2" % OWNER), log())
            label = propose(project, "add", "decisions", draft=draft_of(when="booking a room"))
            self.assertEqual(project.run("reject", label, "--reason", "too rare")[0], 0)
            self.assertTrue(log().endswith("· rejected — too rare"), log())
            self.assertEqual(project.run("reject", label)[0], 3)
            self.assertEqual(errors(project), [])
    def test_add_writes_the_record_the_log_and_the_evidence_and_check_passes(self):
        with started() as project:
            project.run("walk", "start", "--ask", "t")
            _, out, _ = add_notes(project, item(), item(title="A second thing"))
            notes = re.findall(r"O-[0-9]{8}-[0-9a-f]{8}", out)
            label = propose(project, "add", "decisions", draft=draft_of(), evidence=notes)
            self.assertEqual(errors(project), [])
            code, out, err = apply(project, label)
            self.assertEqual(code, 0, out + err)
            self.assertIn("The new record is D-006", out)
            record = project.read("vesta/decisions/D-006.md")
            self.assertRegex(record, r'uid: "?[0-9a-f]{8}"?\n')  # one of digits only is written in quotes
            self.assertNotIn("NEW", record.split("---")[1])
            self.assertIn("decided: 2026-01-05", record)
            self.assertIn("approved-by: %s" % OWNER, record)
            uid = re.search(r'uid: "?([0-9a-f]{8})', record).group(1)
            line = project.read("vesta/log/admissions.md").strip().split("\n")[-1]
            self.assertRegex(line, r"^- 2026-01-05 · %s@[0-9a-f]{8} · add · D-006@%s · approved by %s · evidence 2$" % (label, uid, re.escape(OWNER)))
            for note in notes:
                text = project.read("vesta/observations/archive/direct/%s.md" % note)
                self.assertIn("disposition: promoted → D-006 (%s)" % label, text)
                self.assertFalse(os.path.exists(project.path("vesta/observations/open/%s.md" % note)))
            decided = project.read("vesta/log/proposals/%s.md" % label)
            self.assertIn("outcome: approved by %s, 2026-01-05" % OWNER, decided)
            self.assertTrue(os.path.isfile(project.path("vesta/log/proposals/%s.draft.md" % label)))
            self.assertEqual(os.listdir(project.path("vesta/proposals")).count("%s.md" % label), 0)
            self.assertEqual(project.check(), [line for line in project.check() if line.startswith("warning")])
            self.assertEqual(errors(project), [])
            self.assertFalse(os.path.exists(project.path(trees.JOURNAL)))
            code, out, _ = apply(project, label)
            self.assertEqual(code, 3)
            self.assertIn("already decided", out)

    def test_a_draft_that_does_not_stand_is_refused_and_named(self):
        with started() as project:
            label = propose(project, "add", "decisions", draft=draft_of().replace("- False if: the source is frozen before drafting starts.\n", ""))
            code, out, _ = apply(project, label)
            self.assertEqual(code, 3)
            self.assertIn("cannot be applied as drafted", out)
            self.assertIn("False if", out)
            self.assertTrue(errors(project))
            unfilled = propose(project, "add", "decisions")
            code, out, _ = project.run("proposals", unfilled)
            self.assertIn("placeholder", out)
            self.assertEqual(apply(project, unfilled)[0], 3)

    def test_sessions_is_computed_and_an_edited_figure_fails_the_check(self):
        with started() as project:
            project.run("walk", "start", "--ask", "one")
            _, out, _ = add_notes(project, item())
            first = re.findall(r"O-[0-9]{8}-[0-9a-f]{8}", out)
            project.run("session", "close")
            project.run("walk", "start", "--ask", "two")
            _, out, _ = add_notes(project, item(title="Again"), item(title="And again"))
            second = re.findall(r"O-[0-9]{8}-[0-9a-f]{8}", out)
            label = propose(project, "add", "decisions", draft=draft_of(), evidence=first + second)
            path = "vesta/proposals/%s.md" % label
            self.assertIn("sessions: 2\n", project.read(path))
            self.assertEqual(errors(project), [])
            project.write(path, project.read(path).replace("sessions: 2\n", "sessions: 5\n"))
            found = errors(project)
            self.assertEqual(len(found), 1)
            self.assertIn("error records %s" % path, found[0])
            self.assertIn("`sessions` is 5; the evidence comes from 2 sessions", found[0])

    def test_a_kind_the_configuration_does_not_enable_is_neither_started_nor_applied(self):
        with started() as project:
            label = propose(project, "retire", "D-001", set_block("retired-because: the module is gone"))
            config = mtime_config()
            config["proposals"]["kinds"].remove("retire")
            project.write_config(config)
            project.admit("vesta/vesta.yml")
            for arguments in (("propose", "retire", "--target", "D-002", "--source", "init"), ("apply", label, "--approved-by", OWNER)):
                code, out, _ = project.run(*arguments)
                self.assertEqual(code, 3, arguments)
                self.assertIn("not enabled", out)
            self.assertIn("status: accepted", project.read("vesta/decisions/D-001.md"))

    def test_a_draft_alike_to_a_record_in_force_is_listed_and_nothing_is_refused(self):
        with started() as project:
            project.write("draft.md", draft_of(when="calling an outside service from a job", title="Every figure is checked on the day"))
            code, out, _ = project.run("propose", "add", "--target", "decisions", "--source", "init", "--draft", "draft.md")
            self.assertEqual(code, 0)
            self.assertIn("## Possibly already covered by", out)
            self.assertIn("- D-001, ", out)
            label = LABEL.search(out).group(1)
            self.assertIn("## Possibly already covered by", project.run("proposals", label)[1])
            other = propose(project, "add", "decisions", draft=draft_of(when="ordering stationery", title="Paper is bought quarterly"))
            self.assertNotIn("Possibly already covered", project.run("proposals", other)[1])

    def test_the_list_of_waiting_proposals_and_the_start_notice(self):
        with started() as project:
            self.assertIn("waiting: 0", project.run("proposals")[1])
            label = propose(project, "add", "decisions", draft=draft_of(), title="Sign letters as the owner")
            _, out, _ = project.run("proposals")
            self.assertIn("- %s · add decisions · Sign letters as the owner · standing cost: one short block more read at every start · drafted today" % label, out)
            _, sheet, _ = project.run("walk", "start", "--ask", "t")
            self.assertIn("Proposals waiting for the owner's decision:\n- %s · add decisions" % label, sheet)


class RecordKinds(unittest.TestCase):
    def test_supersede_writes_the_successor_and_flips_the_target_together(self):
        with started() as project:
            label = propose(project, "supersede", "D-001")
            draft = project.read("vesta/proposals/%s.draft.md" % label)
            self.assertIn("supersedes: [D-001@0000000a]", draft)
            self.assertIn("uid: NEW", draft)
            project.write("vesta/proposals/%s.draft.md" % label, draft.replace("calling an outside service", "calling any service outside the project"))
            code, out, err = apply(project, label)
            self.assertEqual(code, 0, out + err)
            old = project.read("vesta/decisions/D-001.md")
            self.assertIn("status: superseded", old)
            self.assertRegex(old, r"superseded-by: D-006@[0-9a-f]{8}")
            self.assertIn("supersedes: [D-001@0000000a]", project.read("vesta/decisions/D-006.md"))
            self.assertEqual(errors(project), [])
            self.assertIn("## Replaced", project.read("vesta/log/proposals/%s.md" % label))
            again = propose(project, "retire", "D-002", set_block("retired-because: gone"))
            code, out, _ = project.run("propose", "supersede", "--target", "D-001", "--source", "init")
            self.assertEqual(code, 2)

    def test_an_interrupted_supersede_is_rolled_back(self):
        with started() as project:
            label = propose(project, "supersede", "D-001")
            before = project.files("vesta")
            real = trees.DiskTree.write
            count = []

            def failing(self, path, text):
                if path.startswith("vesta/decisions/"):
                    count.append(path)
                    if len(count) == 2:
                        raise KeyboardInterrupt()
                return real(self, path, text)

            trees.DiskTree.write = failing
            try:
                with self.assertRaises(KeyboardInterrupt):
                    apply(project, label)
            finally:
                trees.DiskTree.write = real
            self.assertEqual(len(count), 2)
            self.assertNotEqual(project.files("vesta"), before)
            code, out, _ = project.run("version")
            self.assertIn("were put back as they were", out)
            after = project.files("vesta")
            after.pop(trees.JOURNAL, None)
            self.assertEqual(after, before)

    def test_a_target_not_in_force_is_refused(self):
        with started() as project:
            for kind in ("supersede", "retire"):
                code, _, err = project.run("propose", kind, "--target", "D-005", "--source", "init")
                self.assertEqual(code, 2)
                self.assertIn("not in force", err)
            label = propose(project, "supersede", "D-001")
            project.put(decision("D-001", "0000000a", status="retired", retired_because="gone", scopes=["src/http/"], when="calling an outside service"))
            code, out, _ = apply(project, label)
            self.assertEqual(code, 3)
            self.assertIn("not in force", out)

    def test_merge_writes_one_successor_and_flips_every_target(self):
        with started() as project:
            label = propose(project, "merge", "D-001, D-004", draft=draft_of(supersedes=["D-001@0000000a", "D-004@0000000d"], scopes=["src/http/"]))
            code, out, err = apply(project, label)
            self.assertEqual(code, 0, out + err)
            for old in ("D-001", "D-004"):
                text = project.read("vesta/decisions/%s.md" % old)
                self.assertIn("status: superseded", text)
                self.assertRegex(text, r"superseded-by: D-006@[0-9a-f]{8}")
            self.assertEqual(errors(project), [])
            short = propose(project, "merge", "D-002, D-003", draft=draft_of(supersedes=["D-002@0000000b"]))
            code, out, _ = apply(project, short)
            self.assertEqual(code, 3)
            self.assertIn("must name exactly", out)

    def test_retire_latch_edit_and_resolve_trigger(self):
        with started() as project:
            label = propose(project, "retire", "D-002", set_block("retired-because: the guide moved to the wiki"))
            self.assertEqual(apply(project, label)[0], 0)
            text = project.read("vesta/decisions/D-002.md")
            self.assertIn("status: retired", text)
            self.assertIn("retired-because: the guide moved to the wiki", text)
            label = propose(project, "latch-edit", "D-001", set_block("when: calling a service this project does not run\nscopes: [src/http/, src/jobs/]"))
            code, out, err = apply(project, label)
            self.assertEqual(code, 0, out + err)
            text = project.read("vesta/decisions/D-001.md")
            self.assertIn("when: calling a service this project does not run", text)
            self.assertIn("scopes: [src/http/, src/jobs/]", text)
            replaced = project.read("vesta/log/proposals/%s.md" % label)
            self.assertIn("calling an outside service", replaced.split("## Replaced")[1])
            for block, said in (("why: something else\nstatus: retired", "`status`"), ("decided: 2026-02-02", "`decided`")):
                label = propose(project, "latch-edit", "D-001", set_block(block))
                code, out, _ = apply(project, label)
                self.assertEqual(code, 3)
                self.assertIn(said, out)
                self.assertIn("how a record is found", out)
                self.assertEqual(project.run("reject", label, "--by", OWNER, "--reason", "not this way")[0], 0)
            label = propose(project, "resolve-trigger", "D-003/t1", set_block("resolved: the notes moved to docs/changes.md"))
            self.assertEqual(apply(project, label)[0], 0)
            self.assertIn("resolved: the notes moved to docs/changes.md", project.read("vesta/decisions/D-003.md"))
            self.assertNotIn("D-003/t1", project.run("triggers")[1])
            self.assertEqual(project.run("propose", "resolve-trigger", "--target", "D-003/t1", "--source", "init")[0], 2)
            self.assertEqual(errors(project), [])

    def test_correct_changes_wording_and_refuses_the_title_and_the_payload(self):
        with started() as project:
            label = propose(project, "correct", "D-001", pair("Reports are drafted over several days.", "Reports are drafted over a week."))
            self.assertEqual(apply(project, label)[0], 0)
            self.assertIn("drafted over a week", project.read("vesta/decisions/D-001.md"))
            cases = [
                (pair("Every figure is checked on the day it is sent", "x"), "lies in the title"),
                (pair("against the source on the day", "x"), "lies in the section `## Decision`"),
                (pair("no such text", "x"), "occurs nowhere"),
                (pair("the", "x"), "times in the target"),
            ]
            for change, said in cases:
                label = propose(project, "correct", "D-004", change)
                before = project.read("vesta/decisions/D-004.md")
                code, out, _ = apply(project, label)
                self.assertEqual(code, 3, said)
                self.assertIn(said, out)
                self.assertEqual(project.read("vesta/decisions/D-004.md"), before)


class FileKinds(unittest.TestCase):
    ROW = "```vesta-row\nop: add\nid: \"\"\nfires-when: the task changes how a release is cut\nfires-on: scripts/release*\nconsult: \"`docs/`\"\nowed-act: read the checklist before changing a stage\nlevel: standard\n```"

    def test_row_add_change_and_remove(self):
        with started() as project:
            project.write("docs/x.md", "x\n")
            first = propose(project, "row", "walks/start.md", self.ROW)
            code, out, err = apply(project, first)
            self.assertEqual(code, 0, out + err)
            second = propose(project, "row", "walks/start.md", self.ROW.replace("a release is cut", "a tag is made").replace("read the checklist", "read the tagging note"))
            self.assertEqual(apply(project, second)[0], 0)
            text = project.read("vesta/walks/start.md")
            self.assertIn("| start-02 | the task changes how a release is cut | `scripts/release*` | `docs/` | read the checklist before changing a stage | standard | %s |" % first, text)
            self.assertIn("| start-03 | the task changes how a tag is made |", text)
            self.assertEqual(errors(project), [])
            change = propose(project, "row", "walks/start.md", "```vesta-row\nop: change\nid: start-02\nlevel: quiet\n```")
            self.assertEqual(apply(project, change)[0], 0)
            self.assertIn("changing a stage | quiet | %s |" % first, project.read("vesta/walks/start.md"))
            remove = propose(project, "row", "walks/start.md", "```vesta-row\nop: remove\nid: start-02\n```")
            self.assertEqual(apply(project, remove)[0], 0)
            text = project.read("vesta/walks/start.md")
            self.assertNotIn("start-02", text)
            self.assertIn("start-03", text)
            self.assertEqual(errors(project), [])
            _, sheet, _ = project.run("walk", "start", "--ask", "t", "--paths", "scripts/release.sh")
            self.assertIn("- **start-03** (fired)", sheet)
            bad = propose(project, "row", "walks/start.md", "```vesta-row\nop: remove\nid: start-09\n```")
            self.assertEqual(apply(project, bad)[0], 3)

    def test_lens_add_and_a_duplicate_name_is_refused_by_the_checks(self):
        with started() as project:
            block = "```vesta-row\nop: add\nlens: handoff\nangle: What would the next person need that is in nobody's notes?\ncounterfactual: Would they have found it in a minute anyway?\nlevel: standard\n```"
            label = propose(project, "lens", "walks/close.md", block)
            code, out, err = apply(project, label)
            self.assertEqual(code, 0, out + err)
            self.assertIn("| handoff | What would the next person need", project.read("vesta/walks/close.md"))
            again = propose(project, "lens", "walks/start.md", block)
            before = project.files("vesta")
            code, out, _ = apply(project, again)
            self.assertEqual(code, 3)
            self.assertIn("1 error it does not have now", out)
            self.assertIn("used once across the walk files", out)
            self.assertEqual(project.files("vesta"), before)

    def test_language_changes_prose_and_refuses_a_table(self):
        with started() as project:
            text = project.read("vesta/language.md")
            line = [l for l in text.split("\n") if l and not l.startswith(("#", "|", "-", " ", "`")) and text.count(l) == 1][0]
            label = propose(project, "language", "language.md", pair(line, line + " Always."))
            code, out, err = apply(project, label)
            self.assertEqual(code, 0, out + err)
            self.assertIn(line + " Always.", project.read("vesta/language.md"))
            self.assertEqual(errors(project), [])
            label = propose(project, "language", "walks/close.md", pair("| friction |", "| drag |"))
            code, out, _ = apply(project, label)
            self.assertEqual(code, 3)
            self.assertIn("lies in a table", out)

    def test_a_schema_change_under_which_a_record_would_fail_is_refused(self):
        with started() as project:
            label = propose(project, "schema", "decisions/SCHEMA.md", pair("    values: [accepted, superseded, retired]", "    values: [accepted, superseded]"))
            before = project.files("vesta")
            code, out, _ = apply(project, label)
            self.assertEqual(code, 3)
            self.assertIn("D-005", out)
            self.assertEqual(project.files("vesta"), before)
            project.run("reject", label, "--by", OWNER, "--reason", "no")
            label = propose(project, "schema", "decisions/SCHEMA.md", pair("    values: [accepted, superseded, retired]", "    values: [accepted, superseded, retired, parked]"))
            code, out, err = apply(project, label)
            self.assertEqual(code, 0, out + err)
            self.assertEqual(errors(project), [])

    def test_config_sets_a_key_and_refuses_a_value_the_configuration_cannot_hold(self):
        with started() as project:
            label = propose(project, "config", "vesta.yml", set_block("reminders.learn.open-observations: 40\nengagement: quiet"))
            code, out, err = apply(project, label)
            self.assertEqual(code, 0, out + err)
            context = project.context()
            self.assertEqual(context.config.remind_open_observations, 40)
            self.assertEqual(context.config.engagement, "quiet")
            self.assertEqual(errors(project), [])
            label = propose(project, "config", "vesta.yml", set_block("engagement: loud"))
            code, out, _ = apply(project, label)
            self.assertEqual(code, 3)
            self.assertIn("engagement", out)


class Decisions(unittest.TestCase):
    def test_reject_disposes_the_evidence_and_keeps_the_reason(self):
        with started() as project:
            project.run("walk", "start", "--ask", "t")
            _, out, _ = add_notes(project, item())
            note = re.findall(r"O-[0-9]{8}-[0-9a-f]{8}", out)[0]
            label = propose(project, "add", "decisions", draft=draft_of(), evidence=[note])
            for arguments in (("reject", label), ("reject", label, "--by", OWNER)):
                self.assertEqual(project.run(*arguments)[0], 3)
            code, out, err = project.run("reject", label, "--by", OWNER, "--reason", "-", stdin=io.StringIO("it duplicates D-001"))
            self.assertEqual(code, 0, out + err)
            text = project.read("vesta/observations/archive/direct/%s.md" % note)
            self.assertIn("disposition: \"dropped — rejected (%s): it duplicates D-001\"" % label, text.replace("'", '"'))
            self.assertIn("outcome: \"rejected by %s, 2026-01-05: it duplicates D-001\"" % OWNER, project.read("vesta/log/proposals/%s.md" % label).replace("'", '"'))
            self.assertRegex(project.read("vesta/log/admissions.md"), r"· add · decisions · rejected by %s — it duplicates D-001\n" % re.escape(OWNER))
            self.assertFalse(os.path.exists(project.path("vesta/decisions/D-006.md")))
            self.assertEqual(errors(project), [])
            self.assertEqual(project.run("reject", label, "--by", OWNER, "--reason", "again")[0], 3)

    def test_a_record_written_by_hand_is_logged_and_a_schema_edit_is_an_error_until_adopted(self):
        with started() as project:
            project.put(decision("D-009", "000000ff"), admit=False)
            self.assertEqual(errors(project), [])
            self.assertIn("- 2026-01-05 · edit · vesta/decisions/D-009.md · written by hand", project.read("vesta/log/admissions.md"))
            os.remove(project.path("vesta/decisions/D-009.md"))
            self.assertEqual(errors(project), [])
            self.assertIn("· edit · vesta/decisions/D-009.md · removed by hand", project.read("vesta/log/admissions.md"))
            project.write("vesta/decisions/SCHEMA.md", project.read("vesta/decisions/SCHEMA.md") + "\nOne more line.\n")
            found = errors(project)
            self.assertEqual(len(found), 1)
            self.assertIn("error admitted vesta/decisions/SCHEMA.md:1 the file was changed by hand since it was last approved", found[0])
            self.assertIn("`adopt vesta/decisions/SCHEMA.md`", found[0])
            code, out, err = project.run("adopt", "decisions/SCHEMA.md", "--ref", "4e1f0c2")
            self.assertEqual(code, 0, out + err)
            self.assertEqual(errors(project), [])
            self.assertEqual(project.read("vesta/log/admissions.md").strip().split("\n")[-1], "- 2026-01-05 · adopt · vesta/decisions/SCHEMA.md · approved — edited by hand · ref 4e1f0c2")
            self.assertEqual(project.run("adopt", "README.md")[0], 2)
            self.assertIn("as it was last approved", project.run("adopt", project.path("vesta/decisions/SCHEMA.md"))[1])
    def test_the_notes_store_takes_add_latch_edit_and_retire_with_no_engine_change(self):
        with started() as project:
            project.add_notes_store()
            project.admit("vesta/vesta.yml", "vesta/notes/SCHEMA.md")
            draft = front({"uid": "NEW", "id": "NEW", "state": "accepted", "cue": "packing a parcel", "stakes": "", "unless": "", "areas": [], "watch": [], "gone-because": ""})
            draft += "# Parcels are weighed twice\n\n## Note\nWeigh before and after sealing.\n\n- False if: the scale is replaced by a counting one.\n"
            label = propose(project, "add", "notes", draft=draft)
            code, out, err = apply(project, label)
            self.assertEqual(code, 0, out + err)
            self.assertIn("The new record is N-01", out)
            label = propose(project, "latch-edit", "N-01", set_block("cue: packing or re-packing a parcel"))
            self.assertEqual(apply(project, label)[0], 0)
            label = propose(project, "retire", "N-01", set_block("gone-because: parcels are no longer sent"))
            code, out, err = apply(project, label)
            self.assertEqual(code, 0, out + err)
            text = project.read("vesta/notes/N-01.md")
            self.assertIn("state: retired", text)
            self.assertIn("cue: packing or re-packing a parcel", text)
            self.assertEqual(errors(project), [])


class AfterTheReview(unittest.TestCase):
    def test_a_hand_edit_is_logged_and_one_to_a_schema_is_never_written_over(self):
        with started() as project:
            project.write("vesta/language.md", project.read("vesta/language.md") + "\nA rule added by hand.\n")
            project.write("vesta/decisions/D-004.md", project.read("vesta/decisions/D-004.md") + "\nA line added by hand.\n")
            code, out, _ = project.run("index")
            self.assertEqual(code, 0)
            self.assertIn("Note: vesta/language.md was changed by hand; vesta/log/admissions.md now says so.", out)
            log = project.read("vesta/log/admissions.md")
            self.assertIn("- 2026-01-05 · edit · vesta/language.md · changed by hand", log)
            self.assertIn("- 2026-01-05 · edit · vesta/decisions/D-004.md · changed by hand", log)
            self.assertNotIn("Note:", project.run("index")[1])
            self.assertEqual(errors(project), [])
            schema = project.read("vesta/decisions/SCHEMA.md")
            label = propose(project, "schema", "decisions/SCHEMA.md", pair("    values: [accepted, superseded, retired]", "    values: [accepted, superseded, retired, parked]"))
            project.write("vesta/decisions/SCHEMA.md", schema + "\nA line added by hand.\n")
            self.assertEqual(len(errors(project)), 1)
            before = project.files("vesta")
            code, out, _ = apply(project, label)
            self.assertEqual(code, 3, out)
            self.assertIn("Note: vesta/decisions/SCHEMA.md was changed by hand and is not accepted. Until `adopt vesta/decisions/SCHEMA.md`", out)
            self.assertIn("cannot be done while vesta/decisions/SCHEMA.md is changed by hand and not accepted", out)
            self.assertEqual(project.files("vesta"), before)
            self.assertEqual(project.run("adopt", "decisions/SCHEMA.md")[0], 0)
            self.assertEqual(apply(project, label)[0], 0)
    def test_two_stores_never_share_a_prefix(self):
        with started() as project:
            label = propose(project, "config", "vesta.yml", set_block("stores.decisions.label.prefix: P"))
            before = project.files("vesta")
            code, out, _ = apply(project, label)
            self.assertEqual(code, 3)
            self.assertIn("which is also the prefix of the store `", out)
            self.assertEqual(project.files("vesta"), before)

    def test_a_relabel_reaches_text_fields_and_leaves_the_proposal_log_alone(self):
        with started() as project:
            add_notes(project, item(title="Twenty was wanted", via="owner-steer", steer_kind="correction", moment="start", missed_by="D-004", anchor="D-004"))
            waiting = propose(project, "latch-edit", "D-004", set_block("when: choosing any timeout"))
            first = propose(project, "config", "vesta.yml", set_block("stores.decisions.label.prefix: REC\nstores.decisions.label.digits: 4"))
            code, out, err = apply(project, first)
            self.assertEqual(code, 0, out + err)
            note = [text for name, text in project.files("vesta/observations").items() if "/open/" in name][0]
            self.assertIn("missed-by: REC-0004", note)
            self.assertIn("anchor: REC-0004", note)
            self.assertIn("target: REC-0004", project.read("vesta/proposals/%s.md" % waiting))
            self.assertTrue(os.path.isfile(project.path("vesta/log/proposals/%s.md" % first)))
            self.assertEqual(errors(project), [])
            self.assertEqual(apply(project, waiting)[0], 0)

    def test_the_change_made_first_stands_and_a_proposal_it_overtakes_is_closed_as_stale(self):
        with started() as project:
            edit = propose(project, "latch-edit", "D-004", set_block("when: choosing any timeout"))
            trigger = propose(project, "resolve-trigger", "D-003/t2", set_block("resolved: a second product was dropped"))
            gone = propose(project, "retire", "D-004", set_block("retired-because: the module is gone"))
            code, out, err = apply(project, gone)
            self.assertEqual(code, 0, out + err)
            self.assertIn("Note: %s can no longer be applied (D-004 is not in force" % edit, out)
            self.assertIn("%s is closed as stale" % edit, out)
            self.assertNotIn(trigger, out)
            self.assertIn("outcome: 'stale, 2026-01-05: overtaken by %s'" % gone, project.read("vesta/log/proposals/%s.md" % edit).replace('"', "'"))
            self.assertIn("· stale — overtaken by %s" % gone, project.read("vesta/log/admissions.md"))
            code, out, _ = apply(project, edit)
            self.assertEqual(code, 3)
            self.assertIn("already decided", out)
            self.assertNotIn("choosing any timeout", project.read("vesta/decisions/D-004.md"))
            self.assertEqual(project.run("proposals")[1].split("\n")[0], "# Proposals waiting: 1")
            self.assertEqual(errors(project), [])

    def test_two_proposals_may_rest_on_one_note_and_neither_ends_the_other(self):
        with started() as project:
            code, out, _ = add_notes(project, item(title="The owner chose plain numbers", via="owner-steer", steer_kind="choice", moment="start", missed_by="none"))
            evidence = re.findall(r"O-[0-9]{8}-[0-9a-f]{8}", out)
            one = propose(project, "add", "decisions", draft=draft_of(when="sending a letter"), evidence=evidence)
            two = propose(project, "add", "decisions", draft=draft_of(when="posting a parcel"), evidence=evidence)
            three = propose(project, "add", "decisions", draft=draft_of(when="paying an invoice"), evidence=evidence)
            code, out, err = project.run("reject", one, "--reason", "too rare")
            self.assertEqual(code, 0, out + err)
            self.assertNotIn("Note:", out)
            archived = [name for name in project.files("vesta/observations") if "/archive/" in name]
            self.assertEqual(len(archived), 1)
            code, out, err = apply(project, two)
            self.assertEqual(code, 0, out + err)
            self.assertIn("dropped — rejected (%s): too rare" % one, project.read(archived[0]))
            self.assertEqual(project.run("proposals")[1].split("\n")[0], "# Proposals waiting: 1")
            self.assertEqual(apply(project, three)[0], 0)
            self.assertEqual(errors(project), [])

    def test_a_hand_edit_made_first_stands_over_a_waiting_proposal_on_the_same_file(self):
        with started() as project:
            waiting = propose(project, "latch-edit", "D-004", set_block("when: choosing any timeout"))
            other = propose(project, "latch-edit", "D-001", set_block("when: calling any outside service"))
            doomed = propose(project, "retire", "D-002", set_block("retired-because: the guide is gone"))
            project.write("vesta/decisions/D-004.md", project.read("vesta/decisions/D-004.md").replace("when: choosing a timeout", "when: choosing a timeout or a retry count"))
            os.remove(project.path("vesta/decisions/D-002.md"))
            disk = trees.DiskTree(project.root)
            with disk.lock(trees.COMMAND_LOCK):
                self.assertNotIn("Note:", project.run("index")[1])
            code, out, _ = project.run("index")
            self.assertIn("Note: vesta/decisions/D-004.md was changed by hand", out)
            self.assertIn("Note: %s was waiting to change vesta/decisions/D-004.md; the hand edit stands" % waiting, out)
            self.assertIn("Note: %s was waiting to change what a hand edit removed" % doomed, out)
            self.assertNotIn(other, out)
            self.assertEqual(project.read("vesta/log/admissions.md").count("· edit · vesta/decisions/D-004.md"), 1)
            self.assertIn("· stale — overtaken by a hand edit to vesta/decisions/D-004.md", project.read("vesta/log/admissions.md"))
            self.assertEqual(apply(project, waiting)[0], 3)
            self.assertIn("a retry count", project.read("vesta/decisions/D-004.md"))
            self.assertEqual(errors(project), [])
            self.assertEqual(apply(project, other)[0], 0)

    def test_a_schema_or_the_configuration_changed_by_hand_stops_every_change_whatever_the_checks(self):
        with started() as project:
            label = propose(project, "latch-edit", "D-004", set_block("when: choosing any timeout"))
            project.write("vesta/vesta.yml", project.read("vesta/vesta.yml").replace("admitted, ", ""))
            self.assertNotIn("admitted", project.read("vesta/vesta.yml").split("checks:")[1])
            project.write("vesta/proposals/SCHEMA.md", project.read("vesta/proposals/SCHEMA.md") + "\nA line added by hand.\n")
            code, out, _ = project.run("index")
            self.assertEqual(code, 0)
            for path in ("vesta.yml", "proposals/SCHEMA.md"):
                self.assertIn("Note: vesta/%s was changed by hand and is not accepted. Until `adopt vesta/%s`" % (path, path), out)
            before = project.files("vesta")
            code, out, _ = apply(project, label)
            self.assertEqual(code, 3)
            self.assertIn("cannot be done while vesta/proposals/SCHEMA.md, vesta/vesta.yml are changed by hand and not accepted", out)
            self.assertEqual(project.files("vesta"), before)
            self.assertEqual(project.run("adopt", "vesta.yml")[0], 0)
            self.assertEqual(project.run("adopt", "proposals/SCHEMA.md")[0], 0)
            self.assertNotIn("Note:", project.run("index")[1])
            self.assertEqual(apply(project, label)[0], 0)
    def test_a_name_is_read_from_standard_input_and_a_decided_proposal_prints(self):
        with started() as project:
            label = propose(project, "add", "decisions", draft=draft_of())
            code, out, err = project.run("apply", label, "--approved-by", "-", stdin=io.StringIO("A. Reviewer\n"))
            self.assertEqual(code, 0, out + err)
            self.assertIn("approved by A. Reviewer", project.read("vesta/log/admissions.md").strip().split("\n")[-1])
            code, out, _ = project.run("proposals", label)
            self.assertEqual(code, 0)
            self.assertIn("decided, and kept as it was decided", out)
            self.assertIn("outcome: approved by A. Reviewer", out)
    def test_an_add_replaces_nothing(self):
        with started() as project:
            label = propose(project, "add", "decisions", draft=draft_of(supersedes=["D-001@0000000a"]))
            code, out, _ = apply(project, label)
            self.assertEqual(code, 3)
            self.assertIn("an `add` replaces none", out)
    def test_what_propose_refuses_and_what_it_scaffolds(self):
        with started() as project:
            code, _, err = project.run("propose", "add", "--target", "decisions", "--source", "somewhere")
            self.assertEqual(code, 2)
            self.assertIn("is none of: a session id", err)
            code, _, err = project.run("propose", "wish", "--target", "decisions", "--source", "init")
            self.assertEqual(code, 2)
            self.assertIn("is not a kind of proposal", err)
            self.assertEqual(project.run("propose", "add", "--target", "decisions", "--source", "pass-003")[0], 0)
            _, out, _ = project.run("proposals")
            self.assertIn("still being drafted: not ready for a decision", out)
            self.assertNotIn("<fill:", out)
            project.run("propose", "row", "--target", "walks/close.md", "--source", "init")
            project.run("propose", "retire", "--target", "D-004", "--source", "init")
            texts = [text for name, text in sorted(project.files("vesta/proposals").items()) if re.search(r"P-\d+\.md$", name)]
            self.assertNotIn("\nid:", texts[1].split("## Change")[1])
            block = texts[2].split("```vesta-set\n")[1].split("```")[0]
            self.assertEqual(list(yamlsubset.read(block)), ["retired-because"])

    def test_a_linked_file_is_refused_before_anything_is_written(self):
        with started() as project:
            label = propose(project, "language", "walks/close.md", pair("Walked by", "Carried out by"))
            if "Walked by" not in project.read("vesta/walks/close.md"):
                self.skipTest("the close walk has no such line")
            outside = project.path("../outside-%s.md" % os.path.basename(project.root))
            try:
                support.write(outside, project.read("vesta/walks/close.md"))
                os.remove(project.path("vesta/walks/close.md"))
                try:
                    os.symlink(outside, project.path("vesta/walks/close.md"))
                except (OSError, NotImplementedError):
                    self.skipTest("this system makes no links")
                before = project.files("vesta/log")
                code, out, _ = apply(project, label)
                self.assertEqual(code, 3, out)
                self.assertIn("leads outside the project", out)
                self.assertEqual(project.files("vesta/log"), before)
            finally:
                if os.path.exists(outside):
                    os.remove(outside)

    def test_a_deciding_command_waits_its_turn(self):
        with started() as project:
            label = propose(project, "add", "decisions", draft=draft_of())
            disk = trees.DiskTree(project.root)
            with disk.lock(trees.COMMAND_LOCK) as held:
                self.assertTrue(held)
                code, _, err = apply(project, label)
                self.assertEqual(code, 2)
                self.assertIn("another command is changing vesta/", err)
            self.assertEqual(apply(project, label)[0], 0)


class Relabel(unittest.TestCase):
    def test_a_config_proposal_that_changes_a_label_renames_everything(self):
        with started() as project:
            project.put(decision("D-006", "0000000f", related=["D-001@0000000a"]), body=BODY + "\nSee D-001 and D-0011, and D-001/t1.\n")
            project.run("walk", "start", "--ask", "t", "--paths", "src/http/client.py")
            project.run("session", "close")
            uids = dict((name, re.search(r'uid: "?(\w+)', text).group(1)) for name, text in project.files("vesta/decisions").items() if name.endswith(".md") and "/D-" in name)
            label = propose(project, "config", "vesta.yml", set_block("stores.decisions.label.prefix: REC\nstores.decisions.label.digits: 4"))
            code, out, err = apply(project, label)
            self.assertEqual(code, 0, out + err)
            names = sorted(name for name in os.listdir(project.path("vesta/decisions")) if name.startswith(("REC-", "D-")))
            self.assertEqual(names, ["REC-000%d.md" % number for number in range(1, 7)])
            text = project.read("vesta/decisions/REC-0006.md")
            self.assertIn("id: REC-0006", text)
            self.assertIn("related: [REC-0001@0000000a]", text)
            self.assertIn("See REC-0001 and D-0011, and REC-0001/t1.", text)
            self.assertIn('"record": "REC-0001@0000000a"', project.read("vesta/log/consultations.jsonl"))
            self.assertIn("REC-0001@0000000a", project.read("vesta/log/admissions.md"))
            after = dict((name.replace("REC-000", "D-00"), re.search(r'uid: "?(\w+)', text).group(1)) for name, text in project.files("vesta/decisions").items() if "/REC-" in name)
            self.assertEqual(after, uids)
            self.assertEqual(errors(project), [])
            self.assertIn("REC-0001", project.run("index")[1])

    def test_one_record_moves_to_the_next_free_number(self):
        with started() as project:
            project.put(decision("D-006", "0000000f", related=["D-002@0000000b"]), body=BODY + "\nSee D-002.\n")
            code, out, err = project.run("relabel", "decisions", "--one", "D-002")
            self.assertEqual(code, 0, out + err)
            self.assertIn("D-002 to D-007", out)
            self.assertFalse(os.path.exists(project.path("vesta/decisions/D-002.md")))
            self.assertIn("id: D-007", project.read("vesta/decisions/D-007.md"))
            text = project.read("vesta/decisions/D-006.md")
            self.assertIn("related: [D-007@0000000b]", text)
            self.assertIn("See D-007.", text)
            self.assertEqual(errors(project), [])
            self.assertIn("Nothing was changed", project.run("relabel", "decisions")[1])
            self.assertEqual(project.run("relabel", "nowhere")[0], 2)


class CloseSteps(unittest.TestCase):
    def test_choices_prints_the_test_and_each_record_in_force_and_offers_only_when_active(self):
        with started() as project:
            project.run("walk", "start", "--ask", "t")
            add_notes(project, item(title="Blue was chosen over green", via="owner-steer", steer_kind="choice", moment="work", missed_by="none", anchor="owner, 2026-01-05"), item())
            session = project.run("session", "close")[1].split()[1].rstrip(".")
            _, sheet, _ = project.run("walk", "close", "--from", "choices", "--session", session)
            choices = sheet.split("## 8. Choices")[1].split("**Do:**")[0]
            self.assertEqual(len(re.findall(r"O-[0-9]{8}", choices)), 1)
            self.assertIn("Blue was chosen over green", choices)
            self.assertIn("There was a real alternative", choices)
            for label in ("D-001", "D-002", "D-003", "D-004"):
                self.assertIn("- %s  when: " % label, choices)
            self.assertNotIn("D-005", choices)
            self.assertIn("`vesta/decisions/SCHEMA.md`", choices)
            self.assertIn("propose add --target decisions --evidence <that observation> --source %s" % session, sheet)
            self.assertNotIn("Offers", sheet)
        config = mtime_config()
        config["engagement"] = "active"
        with started(config) as project:
            self.assertIn("· 9. Offers ·", project.run("walk", "close")[1])

    def test_the_shipped_configuration_names_only_members_this_engine_has_but_the_learn_steps(self):
        from cli import manifest
        shipped = yamlsubset.read(support.read(os.path.join(fixtures.TEMPLATES, "vesta.yml")))
        known = manifest.known()
        self.assertEqual([kind for kind in shipped["proposals"]["kinds"] if kind not in known["kinds"]], [])
        self.assertEqual([name for name in shipped["checks"]["run"] if name not in known["checks"]], [])
        for name in ("start", "close"):
            self.assertEqual([step for step in shipped["checkpoints"][name]["steps"] if step not in known["steps"]], [])


if __name__ == "__main__":
    unittest.main()
