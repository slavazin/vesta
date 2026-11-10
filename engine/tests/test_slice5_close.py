import io
import json
import os
import re
import sys
import unittest

import support
import fixtures
from fixtures import Project, decision
from cli import manifest
from matchers import probes
from session import log, state
from test_slice4_sessions import GOLDEN, SENTINEL, five, mtime_config, tokens

LABEL = re.compile(r"O-[0-9]{8}-[0-9a-f]{8}")


def item(**changes):
    found = {"title": "The export asks for the date twice", "body": "Both stages prompt for it.", "via": "off-map", "anchor": "src/http/client.py"}
    found.update((name.replace("_", "-"), value) for name, value in changes.items())
    return found


def add(project, *items, **options):
    return project.run("obs", "add", *options.get("arguments", ()), stdin=io.StringIO(json.dumps(list(items))))


def notes(project):
    return sorted(path for path in project.files("vesta/observations") if "/open/" in path)


def worked(project, config=None):
    """A session that started on docs/, then changed src/http/client.py and took one correction."""
    five(project)
    code, out, err = project.run("walk", "start", "--ask", "raise the timeout", "--paths", "docs/guide.md")
    assert code == 0, err
    project.clock.advance(seconds=5)
    project.write("src/http/client.py", "timeout = 20\n")
    at = state.open_ones(project.context().tree)[0].base["at"] + 10 ** 9
    os.utime(project.path("src/http/client.py"), ns=(at, at))
    project.run("jot", "--steer", "-", stdin=io.StringIO("twenty seconds, not thirty"))
    return state.open_ones(project.context().tree)[0].id


def sections(sheet):
    return re.findall(r"^## \d+\. (.+)$", sheet, re.M)


class ObsAdd(unittest.TestCase):
    def test_one_item_that_cannot_stand_writes_nothing_and_is_named(self):
        with Project(init=True, config=mtime_config()) as project:
            project.write("src/a.py", "x\n")
            cases = [
                (item(body="It failed.\nFix: pass the date on."), "a line of the body opens `Fix:`"),
                (item(body="x" * 601), "the body is 601 characters; the most is 600"),
                (item(recheck="exists src/a.py"), "`recheck` fires already"),
                (item(recheck="look src"), "does not read as a probe"),
                (item(via="owner-steer"), "`steer-kind` is empty"),
                (item(via="contradiction", record="D-777"), "names no record"),
                (item(title="  "), "`title` is empty"),
                (item(colour="red"), "`colour` is not a key"),
                (item(disposition="read"), "`disposition` is not a key"),
            ]
            for bad, said in cases:
                code, out, _ = add(project, item(title="A good one"), bad, item(title="Another good one"))
                self.assertEqual(code, 3, said)
                self.assertIn("item 2 (", out)
                self.assertIn(said, out)
                self.assertIn("nothing was written", out)
                self.assertIn("The rule is in vesta/observations/SCHEMA.md", out)
                self.assertNotIn("item 1", out)
                self.assertEqual(notes(project), [])
            code, out, _ = add(project, item(body="Fix: a"), item(body="TODO: b"))
            self.assertIn("item 1 (", out)
            self.assertIn("item 2 (", out)
            self.assertIn("2 of the 2 items", out)

    def test_input_that_is_not_an_array_is_a_usage_error(self):
        with Project(init=True, config=mtime_config()) as project:
            for text in ("", "{}", "[]", "not json"):
                code, _, err = project.run("obs", "add", stdin=io.StringIO(text))
                self.assertEqual(code, 2, text)
                self.assertIn("standard input", err)
            code, out, _ = project.run("obs", "add", stdin=io.StringIO('["a"]'))
            self.assertEqual(code, 3)
            self.assertIn("not a JSON object", out)
            self.assertEqual(project.run("obs")[0], 2)

    def test_the_same_title_twice_gets_two_ids_and_the_records_pass_the_checks(self):
        with Project(init=True, config=mtime_config()) as project:
            project.put(decision("D-001", "0000000a"))
            project.admit("vesta/decisions/D-001.md") if "admitted" in manifest.CHECKS else None
            project.run("walk", "start", "--ask", "t")
            code, out, err = add(project, item(), item(), item(via="contradiction", record="D-001", recheck="exists src/gone.py"))
            self.assertEqual(code, 0, out + err)
            labels = LABEL.findall(out)
            self.assertEqual(len(set(labels)), 3)
            self.assertEqual(len(notes(project)), 3)
            session = state.open_ones(project.context().tree)[0]
            self.assertEqual([entry["id"].split("@")[0] for entry in session.minted], labels)
            text = project.read("vesta/observations/open/%s.md" % labels[2])
            self.assertIn("record: D-001@0000000a", text)
            self.assertIn("session: %s" % session.id, text)
            self.assertIn("disposition: open", text)
            self.assertEqual([line for line in project.check() if "observations" in line], [])

    def test_with_no_open_session_a_late_one_is_opened_and_named(self):
        with Project(init=True, config=mtime_config()) as project:
            code, out, _ = add(project, item())
            self.assertEqual(code, 0)
            self.assertIn("was opened late", out)
            self.assertTrue(state.open_ones(project.context().tree)[0].late)

    def test_what_the_engine_wrote_is_not_a_change_of_the_session(self):
        with Project(init=True, config=mtime_config()) as project:
            project.run("walk", "start", "--ask", "t")
            add(project, item())
            _, out, _ = project.run("session", "show")
            self.assertNotIn("vesta/observations", out)

    def test_list_prints_the_open_ones_in_the_one_line_and_body_form(self):
        with Project(init=True, config=mtime_config()) as project:
            add(project, item(), item(title="A second thing", via="lens:friction"))
            code, out, _ = project.run("obs", "list", "--open")
            self.assertEqual(code, 0)
            self.assertIn("open: 2", out)
            self.assertIn("via: lens:friction", out)
            self.assertIn("  A second thing", out)
            self.assertIn("    Both stages prompt for it.", out)
            self.assertNotIn("uid:", out)
            self.assertIn("pass 3: 0", project.run("obs", "list", "--pass", "3")[1])
            self.assertEqual(project.run("obs", "list", "--pass", "x")[0], 2)
            self.assertEqual(project.run("obs", "list", "--store", "decisions")[0], 2)


class CloseWalk(unittest.TestCase):
    def test_the_two_parts_equal_the_golden_file(self):
        with Project(init=True, config=mtime_config()) as project:
            session = worked(project)
            _, first, _ = project.run("walk", "close")
            add(project, item(via="lens:friction"), item(title="Twenty seconds was wanted", via="owner-steer", steer_kind="correction", moment="start", missed_by="none"))
            project.run("session", "close")
            code, second, err = project.run("walk", "close", "--from", "choices", "--session", session)
            self.assertEqual(code, 0, err)
            sheet = LABEL.sub("O-TOKEN", tokens(first + "\n=====\n\n" + second, project.root))
            path = os.path.join(GOLDEN, "close-sheet.md")
            if os.environ.get("VESTA_WRITE_GOLDEN"):
                support.write(path, sheet)
            self.assertEqual(sheet, support.read(path))

    def test_the_first_part_names_the_command_for_the_second_which_lists_what_was_minted(self):
        with Project(init=True, config=mtime_config()) as project:
            session = worked(project)
            _, first, _ = project.run("walk", "close")
            self.assertEqual(sections(first), ["Bundle", "Marks", "Sweep", "Contradictions", "Steers", "Lenses", "Mint"])
            command = "walk close --from choices --session %s" % session
            self.assertIn("print the next part with `%s`" % command, first)
            _, out, _ = add(project, item(via="lens:friction"), item(title="A second thing"))
            labels = LABEL.findall(out)
            project.run("session", "close")
            code, second, _ = project.run(*command.split())
            self.assertEqual(code, 0)
            self.assertEqual(sections(second), ["Choices", "Surface"])
            for label in labels:
                self.assertIn(label, second)
            self.assertIn("- lens:friction (1)", second)
            self.assertIn("- off-map (1)", second)
            self.assertIn("The walk is complete", second)
            self.assertIn("Give the owner the close report now", second)

    def test_sweep_prints_an_unloaded_record_that_covers_a_changed_path_and_omits_a_loaded_one(self):
        with Project(init=True, config=mtime_config()) as project:
            worked(project)
            project.run("load", "D-004")
            _, sheet, _ = project.run("walk", "close")
            sweep = sheet.split("## 3. Sweep")[1].split("## 4.")[0]
            self.assertIn("---- D-001, in full", sweep)
            self.assertNotIn("D-004", sweep)
            self.assertNotIn("D-002", sweep)
            self.assertNotIn("D-005", sweep)
            contradictions = sheet.split("## 4. Contradictions")[1].split("## 5.")[0]
            for label in ("D-002", "D-004", "D-001"):
                self.assertIn("**%s," % label, contradictions)
            self.assertIn("False if: the source is frozen", contradictions)
            code, out, _ = project.run("mark", "D-001=should-have-loaded")
            self.assertEqual(code, 0)
            self.assertNotIn("---- D-001", project.run("walk", "close")[1].split("## 3. Sweep")[1].split("## 4.")[0])

    def test_steers_prints_the_captured_corrections_and_only_id_and_when_of_each_record(self):
        with Project(init=True, config=mtime_config()) as project:
            worked(project)
            _, sheet, _ = project.run("walk", "close", "--short")
            steers = sheet.split("## 3. Steers")[1].split("**Do:**")[0]
            self.assertIn("twenty seconds, not thirty (from jot)", steers)
            listed = [line for line in steers.split("\n") if line.startswith("- D-")]
            self.assertEqual(listed, [
                "- D-001  when: calling an outside service",
                "- D-002  when: writing the user guide",
                "- D-003  when: naming a release",
                "- D-004  when: choosing a timeout",
            ])
            for other in ("Every figure", "a stale figure", "src/http", "release notes"):
                self.assertNotIn(other, steers)

    def test_the_short_form_prints_exactly_the_short_steps(self):
        with Project(init=True, config=mtime_config()) as project:
            worked(project)
            code, sheet, _ = project.run("walk", "close", "--short")
            self.assertEqual(code, 0)
            self.assertEqual(sections(sheet), ["Bundle", "Marks", "Steers", "Mint"])
            self.assertIn("(short form)", sheet)
            self.assertIn("The walk is complete", sheet)

    def test_with_no_open_session_a_late_one_is_opened_and_the_bundle_says_so(self):
        with Project(init=True, config=mtime_config()) as project:
            code, sheet, _ = project.run("walk", "close", "--ask", "-", stdin=io.StringIO("tidied the guide"))
            self.assertEqual(code, 0)
            self.assertIn("was opened late", sheet.split("## 1.")[0])
            bundle = sheet.split("## 1. Bundle")[1].split("**Do:**")[0]
            self.assertIn("It was opened late", bundle)
            self.assertIn("1. tidied the guide", bundle)

    def test_closing_logs_each_record_with_its_mark_and_a_bare_session_logs_one_line(self):
        with Project(init=True, config=mtime_config()) as project:
            worked(project)
            project.run("load", "D-004")
            project.run("mark", "D-004=applied")
            project.run("session", "close")
            project.run("walk", "start", "--ask", "nothing much")
            project.run("session", "close")
            lines = log.read(project.context().tree)
            self.assertEqual([(line["record"].split("@")[0], line["by"], line["mark"]) for line in lines], [
                ("D-002", "scope", "unmarked"), ("D-004", "index", "applied"), ("", "", "none-matched"),
            ])

    def test_at_the_active_level_offers_joins_the_second_part(self):
        config = mtime_config()
        config["engagement"] = "active"
        with Project(init=True, config=config) as project:
            session = worked(project)
            _, first, _ = project.run("walk", "close")
            self.assertIn("--from choices --session", first)
            add(project, item(via="lens:friction"), item(title="Another"))
            _, second, _ = project.run("walk", "close", "--from", "choices", "--session", session)
            self.assertEqual(sections(second), ["Choices", "Offers", "Surface"])
            offers = second.split("## 9. Offers")[1].split("**Do:**")[0]
            self.assertEqual(len(LABEL.findall(offers)), 1)
            self.assertIn("There was a real alternative", offers)

    def test_a_close_row_fires_on_a_changed_path(self):
        with Project(init=True, config=mtime_config()) as project:
            text = project.read("vesta/walks/close.md").replace(
                "|---|---|---|---|---|---|---|\n",
                "|---|---|---|---|---|---|---|\n| http | the client changed | `src/http/**` | `docs/` | run the smoke test | quiet | seed |\n| other | a letter went out | `letters/**` | `docs/` | file a copy | quiet | seed |\n", 1)
            project.write("vesta/walks/close.md", text)
            worked(project)
            _, sheet, _ = project.run("walk", "close")
            self.assertIn("- **http** (fired)", sheet)
            self.assertIn("- **other** (judge)", sheet)
            self.assertIn("for the work this session did", sheet)

    def test_a_capture_source_the_configuration_does_not_name_is_not_imported(self):
        sys.modules.pop("adapters.jot", None)
        config = mtime_config()
        config["adapters"]["capture"] = []
        with Project(init=True, config=config) as project:
            worked(project)
            _, sheet, _ = project.run("walk", "close", "--short")
            self.assertNotIn("adapters.jot", sys.modules)
            self.assertIn("Corrections captured while the session ran:\nnone", sheet)

    def test_a_learn_reminder_prints_one_count_at_the_start_and_at_the_close(self):
        config = mtime_config()
        config["reminders"]["learn"]["open-observations"] = 2
        with Project(init=True, config=config) as project:
            add(project, item(), item(title="Another"))
            project.run("session", "close")
            _, start, _ = project.run("walk", "start", "--ask", "t")
            self.assertIn("learn pass due: 2 notes are open", start)
            session = state.open_ones(project.context().tree)[0].id
            project.run("session", "close")
            _, close, _ = project.run("walk", "close", "--from", "surface", "--session", session)
            self.assertIn("learn pass due: 2 notes are open", close)


class AfterTheReview(unittest.TestCase):
    def test_a_later_part_with_no_session_named_is_refused_and_names_the_last_one(self):
        with Project(init=True, config=mtime_config()) as project:
            session = worked(project)
            project.run("session", "close")
            code, out, _ = project.run("walk", "close", "--from", "surface")
            self.assertEqual(code, 3)
            self.assertIn("--session %s" % session, out)
            self.assertEqual(state.open_ones(project.context().tree), [])
            _, sheet, _ = project.run("walk", "close", "--session", session)
            self.assertIn("This session is closed", sheet.split("## 1.")[0])

    def test_a_closed_session_takes_no_observation(self):
        with Project(init=True, config=mtime_config()) as project:
            session = worked(project)
            project.run("session", "close")
            code, out, _ = add(project, item(), arguments=("--session", session))
            self.assertEqual(code, 3)
            self.assertEqual(notes(project), [])

    def test_text_that_cannot_be_written_is_named_by_item_and_a_list_field_takes_a_list(self):
        with Project(init=True, config=mtime_config()) as project:
            code, out, _ = add(project, item(), item(anchor="a\nb"))
            self.assertEqual(code, 3)
            self.assertIn("item 2 (", out)
            self.assertEqual(notes(project), [])
            self.assertEqual(project.run("obs", "add", stdin=io.StringIO("[" * 100000))[0], 2)
            self.assertEqual(project.run("obs", "add", stdin=io.StringIO("\ufeff" + json.dumps([item()])))[0], 0)

    def test_an_open_session_says_so_and_does_not_take_a_second_ask(self):
        with Project(init=True, config=mtime_config()) as project:
            worked(project)
            _, sheet, _ = project.run("walk", "close", "--ask", "-", stdin=io.StringIO("something else"))
            head = sheet.split("## 1.")[0]
            self.assertIn("It was already open: opened 2026-01-05T09:00:00Z.", head)
            self.assertIn("The text given with `--ask` was not recorded", head)

    def test_an_unfinished_change_is_not_undone_while_its_writer_holds_the_lock(self):
        from kernel import tree as trees
        with Project(init=True, config=mtime_config()) as project:
            disk = trees.DiskTree(project.root)
            disk.write(trees.JOURNAL, json.dumps({"paths": {"vesta/language.md": "old\n"}}))
            with disk.lock(trees.COMMIT_LOCK) as held:
                self.assertTrue(held)
                # What is on disk is half of a change: a command neither undoes it nor reads past it.
                code, _, err = project.run("index")
                self.assertEqual(code, 2)
                self.assertIn("part-way through", err)
            self.assertEqual(trees.recover(trees.DiskTree(project.root)), ["vesta/language.md"])


class ZeroCost(unittest.TestCase):
    def test_neither_part_of_the_close_sheet_prints_an_observation_or_evaluates_its_probe(self):
        config = mtime_config()
        config["engagement"] = "active"
        with Project(init=True, config=config) as project:
            session = worked(project)
            add(project, item(via="lens:friction", recheck="missing src/%s" % SENTINEL))
            for path in notes(project):
                text = project.read(path)
                title = [line for line in text.split("\n") if line.startswith("# ")][0]
                project.write(path, text.replace(title, "# %s" % SENTINEL).replace("Both stages prompt for it.", SENTINEL + " body"))
            seen = []
            real = probes.evaluate

            def watching(text, context):
                seen.append(text)
                return real(text, context)

            probes.evaluate = watching
            try:
                _, first, _ = project.run("walk", "close")
                _, second, _ = project.run("walk", "close", "--from", "offers", "--session", session)
                _, short, _ = project.run("walk", "close", "--short")
            finally:
                probes.evaluate = real
            self.assertIn("## 10. Surface", second)
            self.assertNotIn(SENTINEL, first + second + short)
            self.assertFalse([text for text in seen if SENTINEL in str(text)])


class InsightSkill(unittest.TestCase):
    def test_the_skill_names_only_commands_the_engine_has_and_carries_the_rules(self):
        text = " ".join(support.read(os.path.join(support.REPO, "skills", "vesta-insight", "SKILL.md")).split())
        used = set(re.findall(r"`vesta ([a-z]+)", text))
        self.assertEqual(used - set(manifest.COMMANDS), set())
        self.assertTrue({"walk", "obs", "session", "jot", "version"} <= used)
        rule = (
            "Run `apply` only for a proposal the owner has approved by its id in this conversation, after seeing its text. "
            "\"Looks good\", silence, an approval of a different proposal, and an approval given before the proposal was shown "
            "are not approval. Running `apply` is the record that the owner approved; `--ref` may add a commit or a note to it. "
            "Make every lasting change through a proposal. A file under `vesta/` that the owner edits by hand is logged by the "
            "engine; never edit a `SCHEMA.md` or `vesta.yml` by hand."
        )
        for phrase in (rule, "Nothing forces this skill to be run", "carried out honestly", "cannot tell whether the owner approved it", "walk close", "--short", "--ask -"):
            self.assertIn(phrase, text)

    def test_every_step_text_names_only_commands_the_engine_has_or_will_have(self):
        folder = os.path.join(support.ENGINE, "steps", "text")
        later = {"apply", "reject", "propose", "proposals"}
        for leaf in sorted(os.listdir(folder)):
            text = support.read(os.path.join(folder, leaf))
            for word in re.findall(r"[Rr]un `([a-z]+)", text):
                self.assertIn(word, set(manifest.COMMANDS) | later, "%s names `%s`" % (leaf, word))


if __name__ == "__main__":
    unittest.main()
