"""Settings of a person and a machine: which harness, who notes the owner's corrections, and who
carries out the first part of the review; and the copies of a conversation that do that work aside."""
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import unittest

import support
from fixtures import Project
from adapters import in_claude_code, in_other
from cli import manifest
from cli.commands import aside as aside_command
from session import asides, history, settings, state
from steps import instruction
from test_slice9_backfill import BUILT, Home, TALK, add_note, note, notes, said

NAME = "11111111-2222-3333-4444-555555555555"
IN_CLAUDE = {"CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": NAME}
BEFORE = said("user", "add a retry to the fetch", "2026-01-05T08:59:00Z")
DURING = said("user", "no, never sleep in the fetch path; use the backoff helper", "2026-01-05T09:10:00Z")
AGENT = said("assistant", [{"type": "text", "text": "I added three retries with a sleep between them."}], "2026-01-05T09:05:00Z")


def in_claude(project, **more):
    """The project as Claude Code would start its commands. `Home.keep(NAME, …)` keeps the running conversation."""
    project.environ = dict(IN_CLAUDE, **more)
    return project


def choose(project, name, answer):
    code, out, err = project.run("setting", name, answer)
    assert code == 0, out + err
    return out


def start(project, ask="add a retry"):
    code, out, err = project.run("walk", "start", "--ask", ask)
    assert code == 0, out + err
    return out, state.open_ones(project.context().tree)[0]


def close(project, *more):
    code, out, err = project.run("walk", "close", *more)
    assert code == 0, out + err
    return out


def texts():
    return sorted(leaf[:-3] for leaf in os.listdir(instruction.FOLDER) if leaf.endswith(".md"))


class Settings(unittest.TestCase):
    def test_each_is_printed_as_it_stands_and_one_with_every_answer(self):
        with Project(init=True) as project:
            code, out, err = project.run("setting")
            self.assertEqual(code, 0, err)
            for name in manifest.SETTINGS:
                self.assertIn("- `%s`:" % name, out)
            self.assertIn("vesta/.state/settings.json", out)
            self.assertIn("`other` (not chosen", out)
            for name in manifest.SETTINGS:
                code, out, err = project.run("setting", name)
                self.assertEqual(code, 0, err)
                resolved = settings.resolve(project.context(), name)
                self.assertGreater(len(resolved.setting.options), 1)
                for value, line in resolved.setting.options:
                    self.assertIn("- `%s`: %s" % (value, line), out)
                    self.assertTrue(line.strip())

    def test_an_answer_is_kept_forgotten_and_never_committed(self):
        with in_claude(Project(init=True)) as project, Home(project) as home:
            home.keep(NAME, [BEFORE])
            self.assertIn("Kept for `jotting`: `later` (chosen).", choose(project, "jotting", "later"))
            self.assertEqual(json.loads(project.read("vesta/.state/settings.json")), {"jotting": "later"})
            self.assertIn(".state/", project.read("vesta/.gitignore"))
            code, out, _ = project.run("setting", "jotting", "--clear")
            self.assertIn("was forgotten", out)
            self.assertIn("`here` (not chosen", out)
            code, out, _ = project.run("setting", "jotting", "--clear")
            self.assertIn("Nothing was chosen", out)
            code, out, err = project.run("check")
            self.assertEqual(code, 0, out + err)

    def test_what_the_command_line_gives_wrongly_is_refused_by_name_and_nothing_is_written(self):
        with Project(init=True) as project:
            for arguments, wanted in (
                (("setting", "nope"), "`nope` is not a setting; the settings are: harness, jotting, review"),
                (("setting", "jotting", "soon"), "`soon` is not an answer of `jotting`; its answers are: here, later, aside"),
                (("setting", "jotting", "here", "later"), "takes a name and one answer"),
                (("setting", "--clear"), "takes the name of a setting"),
                (("setting", "jotting", "here", "--clear"), "takes no answer"),
                (("setting", "jotting", "--loud"), "`--loud` is not an option"),
                (("setting", "jotting", ""), "`` is not an answer"),
                (("setting", "jotting", "a\nb"), "is not an answer"),
            ):
                code, out, err = project.run(*arguments)
                self.assertEqual(code, 2, arguments)
                self.assertIn(wanted, err)
                self.assertNotIn("did not expect", err)
            self.assertFalse(os.path.exists(project.path("vesta/.state/settings.json")))

    def test_a_file_that_does_not_read_is_named_and_stops_neither_doctor_nor_a_sheet(self):
        with Project(init=True) as project:
            for bad in ("{", "[]", '{"jotting": 3}', "\xff", '{"jotting": ["later"]}'):
                project.write("vesta/.state/settings.json", bad)
                code, out, err = project.run("setting")
                self.assertEqual(code, 2, bad)
                self.assertIn("vesta/.state/settings.json does not read", err)
                self.assertIn("may be deleted by hand", err)
                code, out, err = project.run("doctor")
                self.assertEqual(code, 0, err)
                self.assertIn("- Settings on this machine: vesta/.state/settings.json does not read", out)
                code, out, err = project.run("walk", "start", "--ask", "a task", "--new")
                self.assertEqual(code, 0, err)
                self.assertIn("What was chosen for the setting `jotting` on this machine cannot be read, so the text above is the one for `here`", out)
                self.assertIn("run `jot --steer -`", out)
                self.assertNotIn("did not expect", out + err)

    def test_an_answer_the_engine_no_longer_has_counts_for_nothing_and_is_said(self):
        with in_claude(Project(init=True)) as project:
            project.write("vesta/.state/settings.json", json.dumps({"jotting": "sometimes", "colour": "blue"}))
            code, out, err = project.run("setting", "jotting")
            self.assertEqual(code, 0, err)
            self.assertIn("`here` (not chosen", out)
            self.assertIn("`sometimes` was chosen before and is no answer of it", out)
            choose(project, "jotting", "later")
            self.assertEqual(json.loads(project.read("vesta/.state/settings.json")), {"jotting": "later", "colour": "blue"})

    def test_several_commands_choosing_at_once_leave_a_file_that_reads(self):
        with Project(init=True) as project:
            root = os.path.join(project.root, "my project")
            os.makedirs(os.path.join(root, "vesta"))
            shutil.copytree(BUILT, os.path.join(root, "vesta", ".engine"))
            engine = [sys.executable, os.path.join(root, "vesta", ".engine")]
            self.assertEqual(subprocess.run(engine + ["init"], capture_output=True).returncode, 0)
            wanted = [("jotting", "here"), ("review", "here"), ("harness", "other"), ("jotting", "later"), ("review", "aside"), ("harness", "claude-code")]
            running = [subprocess.Popen(engine + ["setting", name, answer], stdout=subprocess.PIPE, stderr=subprocess.PIPE) for name, answer in wanted]
            results = [(process.communicate(), process.returncode) for process in running]
            for (out, err), code in results:
                self.assertIn(code, (0, 2), err)
                if code == 2:
                    self.assertIn(b"Run this command again", err)
            kept = json.loads(support.read(os.path.join(root, "vesta", ".state", "settings.json")))
            done = [pair for pair, (_, code) in zip(wanted, results) if code == 0]
            self.assertEqual(sorted(kept), sorted(set(name for name, _ in done)))
            for name, answer in kept.items():
                self.assertIn((name, answer), done)


class Harness(unittest.TestCase):
    def test_it_is_found_from_where_the_command_was_started_and_a_choice_outranks_that(self):
        with Project(init=True) as project:
            self.assertIn("`other` (not chosen", project.run("setting", "harness")[1])
            in_claude(project)
            self.assertIn("`claude-code` (found by the engine)", project.run("setting", "harness")[1])
            choose(project, "harness", "other")
            self.assertIn("`other` (chosen)", project.run("setting", "harness")[1])
            self.assertIn("in effect: `here`, because the engine cannot read the conversations of a harness the engine knows nothing of",
                          choose(project, "jotting", "aside"))

    def test_every_harness_is_named_in_the_manifest_states_its_limit_and_one_assumes_nothing(self):
        members = [manifest.member("harnesses", name) for name in manifest.HARNESSES]
        for member in members:
            self.assertTrue(member.name and member.residue)
        self.assertEqual([member.id for member in members if not member.known], ["other"])
        self.assertFalse(in_other.InOther(IN_CLAUDE).here())
        for environ, running in (({}, False), ({"CLAUDECODE": "0"}, False), ({"CLAUDECODE": "1"}, True)):
            self.assertEqual(in_claude_code.InClaudeCode(environ).here(), running)
        for bad in ("", "../x", "a b", "-x", "a\nb", "x" * 200):
            self.assertEqual(in_claude_code.InClaudeCode({"CLAUDE_CODE_SESSION_ID": bad}).conversation(), "")

    def test_the_command_that_starts_a_copy_runs_no_hook_keeps_no_file_and_allows_only_what_it_is_given(self):
        command = in_claude_code.InClaudeCode(IN_CLAUDE).fork(NAME, "do one thing", ['python3 "/a b/vesta/.engine" aside'], reads=True)
        self.assertEqual(command[:5], ["claude", "-p", "--resume", NAME, "--fork-session"])
        self.assertIn("--no-session-persistence", command)
        self.assertEqual(json.loads(command[command.index("--settings") + 1]), {"disableAllHooks": True})
        allowed = command[command.index("--allowedTools") + 1:command.index("--")]
        self.assertEqual(allowed, ['Bash(python3 "/a b/vesta/.engine" aside *)', "Read", "Grep", "Glob"])
        self.assertEqual(command[-2:], ["--", "do one thing"])
        path, entry = in_claude_code.InClaudeCode(IN_CLAUDE).hook("x aside")
        self.assertEqual(path, ".claude/settings.local.json")
        self.assertEqual(json.loads(entry)["hooks"]["UserPromptSubmit"][0]["hooks"][0], {"type": "command", "command": "x aside", "async": True})

    def test_an_answer_the_harness_cannot_carry_out_falls_back_and_says_why(self):
        with Project(init=True) as project, Home(project) as home:
            for kept, environ, chosen, effect, why in (
                (True, {}, "later", "here", "cannot read the conversations of"),
                (True, {}, "aside", "here", "cannot read the conversations of"),
                (True, {"CLAUDECODE": "1"}, "later", "here", "did not say which conversation"),
                (True, {"CLAUDECODE": "1"}, "aside", "here", "did not say which conversation"),
                (False, IN_CLAUDE, "later", "here", "does not find this conversation where Claude Code keeps them (there is no folder"),
                (False, IN_CLAUDE, "aside", "here", "does not find this conversation"),
                (True, dict(IN_CLAUDE, CLAUDE_CODE_SESSION_ID="another"), "later", "here", "(no file of that name is there)"),
                (True, IN_CLAUDE, "later", "later", ""),
                (True, IN_CLAUDE, "aside", "aside", ""),
                (True, IN_CLAUDE, "here", "here", ""),
            ):
                if kept:
                    home.keep(NAME, [BEFORE])
                elif os.path.isdir(home.root):
                    shutil.rmtree(home.root)
                project.environ = environ
                choose(project, "jotting", chosen)
                resolved = settings.resolve(project.context(), "jotting")
                self.assertEqual((resolved.value, resolved.effect), (chosen, effect), environ)
                self.assertIn(why, resolved.why)
                self.assertEqual(bool(why), "in effect:" in settings.said(resolved))
            for environ, effect in (({}, "here"), ({"CLAUDECODE": "1"}, "here"), (IN_CLAUDE, "aside")):
                project.environ = environ
                choose(project, "review", "aside")
                self.assertEqual(settings.in_effect(project.context(), "review"), effect)

    def test_choosing_an_answer_says_what_holds_from_now_on_in_the_task(self):
        with in_claude(Project(init=True)) as project, Home(project) as home:
            home.keep(NAME, [BEFORE])
            self.assertIn("From now on in this task: note no correction of the owner's as it comes; what the owner says is read back", choose(project, "jotting", "later"))
            self.assertIn("From now on in this task: at the moment the owner corrects or redirects the work, run `jot --steer -`", choose(project, "jotting", "here"))
            self.assertIn("a copy of the conversation notes it", choose(project, "jotting", "aside"))
            project.environ = {}
            out = choose(project, "jotting", "later")  # it falls back here, and the instruction is the one in effect
            self.assertIn("run `jot --steer -`", out)
            self.assertNotIn("read back from the conversation when", out)


class SheetText(unittest.TestCase):
    def test_every_setting_a_shipped_text_names_is_one_the_engine_has_with_those_answers(self):
        with Project(init=True) as project:
            context, seen = project.context(), set()
            for name in texts():
                for setting, answers in instruction.conditions(instruction.read(name)):
                    known = [value for value, _ in settings.member(context, setting).options]
                    for answer in answers:
                        self.assertIn(answer, known, name)
                    seen.add(setting)
            self.assertEqual(seen, {"jotting"})

    def test_a_text_that_branches_on_a_setting_prints_no_mark_and_differs_by_the_answer(self):
        with in_claude(Project(init=True)) as project, Home(project) as home:
            home.keep(NAME, [BEFORE])
            for name in texts():
                text = instruction.read(name)
                by_setting = {}
                for setting, answers in instruction.conditions(text):
                    by_setting.setdefault(setting, []).extend(answers)
                for setting, answers in by_setting.items():
                    options = [value for value, _ in settings.member(project.context(), setting).options]
                    printed = {}
                    for option in options:
                        choose(project, setting, option)
                        printed[option] = instruction.fill(text, project.context())
                        self.assertNotIn("[%s:" % setting, printed[option])
                    self.assertGreater(len(set(printed.values())), 1, name)
                    project.run("setting", setting, "--clear")

    def test_the_start_sheet_says_who_notes_corrections_in_the_words_of_the_answer_in_effect_only(self):
        with in_claude(Project(init=True)) as project, Home(project) as home:
            home.keep(NAME, [BEFORE])
            habit = {"here": "run `jot --steer -` and give their words", "later": "is read back from this conversation when the task is reviewed",
                     "aside": "a copy of this conversation is started aside"}
            for answer, wanted in habit.items():
                choose(project, "jotting", answer)
                out, _ = start(project)
                self.assertIn(wanted, out)
                for other, unwanted in habit.items():
                    if other != answer:
                        self.assertNotIn(unwanted, out)
                self.assertNotIn("Not settled on this machine yet", out)
                project.run("session", "abandon", state.open_ones(project.context().tree)[0].id)

    def test_the_question_is_put_once_a_sheet_while_it_is_open_and_only_with_answers_that_can_take_effect(self):
        with Project(init=True) as project:
            out, session = start(project)
            self.assertNotIn("Not settled on this machine yet", out)  # one answer can take effect here: nothing to ask
            self.assertIn("run `jot --steer -`", out)
            project.run("session", "abandon", session.id)
            in_claude(project)
            with Home(project) as home:
                home.keep(NAME, [BEFORE])
                self._asked(project)

    def _asked(self, project):
            out, session = start(project)
            self.assertEqual(out.count("Not settled on this machine yet. Who notes the owner's corrections"), 1)
            for answer in ("here", "later", "aside"):
                self.assertIn("\n- `%s`: " % answer, out)
            self.assertIn("`setting jotting <answer>`", out)
            self.assertIn("Until one is chosen, `here` is in effect.", out)
            self.assertIn("run `jot --steer -`", out)
            choose(project, "jotting", "here")
            project.run("session", "abandon", session.id)
            self.assertNotIn("Not settled on this machine yet", start(project)[0])
            project.run("setting", "jotting", "--clear")
            session = state.open_ones(project.context().tree)[0]
            out = project.run("walk", "close", "--here", environ=dict(project.environ, VESTA_ASIDE="walk"))[1]
            self.assertNotIn("Not settled on this machine yet", out)  # a copy answers nobody, so nothing is asked of it
            self.assertIn("Not settled on this machine yet", close(project))

    def test_the_sheet_of_a_project_started_outside_any_known_harness_is_the_one_it_always_was(self):
        with Project(init=True) as project:
            out, _ = start(project)
            self.assertIn("Then start the work, and keep two habits while working. At the moment the owner corrects or redirects the work, run `jot --steer -`", out)
            self.assertNotIn("conversation", state.open_ones(project.context().tree)[0].data)


def later(project, home, entries, answer="later"):
    """A task started in Claude Code with the conversation kept so far, and `jotting` chosen."""
    in_claude(project)
    choose(project, "jotting", answer)
    home.keep(NAME, entries)
    return start(project)[1]


class Later(unittest.TestCase):
    def test_the_review_prints_what_the_owner_said_since_the_task_began_and_nothing_from_before(self):
        with Project(init=True) as project, Home(project) as home:
            session = later(project, home, [BEFORE])
            self.assertEqual(session.data["conversation"], {"harness": "claude-code", "name": NAME})
            home.keep(NAME, [BEFORE, AGENT, DURING])
            out = close(project)
            self.assertIn("What the owner said since 2026-01-05T09:00:00Z, read from the conversation as Claude Code keeps it", out)
            self.assertIn(": 1 piece.", out)
            self.assertIn("> no, never sleep in the fetch path; use the backoff helper", out)
            self.assertIn("Just before it, the agent said: I added three retries", out)
            self.assertNotIn("> add a retry to the fetch", out)
            self.assertIn("they were read from the conversation as it is kept", out)
            self.assertEqual(close(project).count("> no, never sleep"), 1)  # printed again as it was, and recorded once
            (entry,) = history.read(project.context().tree)
            self.assertEqual((entry["session"], len(entry["marks"]), entry["until"]), (session.id, 1, "2026-01-05T09:10:00Z"))

    def test_what_was_said_in_the_second_the_task_began_is_the_tasks(self):
        with Project(init=True) as project, Home(project) as home:
            later(project, home, [BEFORE])
            home.keep(NAME, [BEFORE, said("user", "use tabs here", "2026-01-05T09:00:00.412Z")])
            self.assertIn("> use tabs here", close(project))

    def test_what_a_review_read_is_not_read_back_again_unless_the_task_was_left_with_no_note(self):
        with Project(init=True) as project, Home(project) as home:
            session = later(project, home, [BEFORE])
            home.keep(NAME, [BEFORE, DURING])
            close(project)
            project.environ = {}
            code, out, _ = project.run("walk", "backfill", "--source", "claude-code", "--conversation", NAME)
            self.assertEqual(code, 0, out)
            self.assertIn("Left out: 1 thing said that was read back before or is being read now", out)
            self.assertNotIn("never sleep", out)
            reading = [found for found in state.reading_back(project.context().tree)][0]
            self.assertNotEqual(reading.id, session.id)  # the task's own session is never taken for one that reads back
            project.run("session", "abandon", reading.id)
            project.run("session", "abandon", session.id)
            project.run("history", "forget", "claude-code", NAME)
            code, out, _ = project.run("walk", "backfill", "--source", "claude-code", "--conversation", NAME)
            self.assertIn("> no, never sleep in the fetch path", out)

    def test_a_reviewed_task_counts_as_read_and_the_next_task_takes_what_was_said_since(self):
        with Project(init=True) as project, Home(project) as home:
            session = later(project, home, [BEFORE])
            home.keep(NAME, [BEFORE, DURING])
            close(project)
            add_note(project, session)
            self.assertEqual(project.run("session", "close", "--session", session.id)[0], 0)
            after = said("user", "and one more thing: never log the token", "2026-01-05T09:20:00Z")
            project.clock.advance(seconds=3600)
            home.keep(NAME, [BEFORE, DURING, after])
            start(project, "a second task")
            home.keep(NAME, [BEFORE, DURING, after, said("user", "prefer early returns", "2026-01-05T10:05:00Z")])
            out = close(project)
            self.assertIn("What the owner said since 2026-01-05T09:10:00Z", out)  # from the last thing read, not from the second task's opening
            self.assertIn("> and one more thing: never log the token", out)
            self.assertIn("> prefer early returns", out)
            self.assertNotIn("> no, never sleep", out)
            project.environ = {}
            code, out, _ = project.run("history", "list", "claude-code")
            self.assertIn("with something to read back\n\n- `%s`" % NAME, out)  # what came before the first task is still there to read back
            self.assertIn("1 piece to read", out)

    def test_a_task_reviewed_without_a_start_takes_everything_not_yet_read(self):
        with in_claude(Project(init=True)) as project, Home(project) as home:
            choose(project, "jotting", "later")
            home.keep(NAME, [BEFORE, DURING])
            out = close(project, "--ask", "what was done")
            self.assertIn("What the owner said, read from", out)
            self.assertIn("> add a retry to the fetch", out)
            self.assertIn("> no, never sleep", out)

    def test_a_conversation_that_cannot_be_read_is_said_and_the_sheet_goes_on(self):
        with Project(init=True) as project, Home(project) as home:
            session = later(project, home, [BEFORE])
            os.remove(os.path.join(home.folder, NAME + ".jsonl"))
            out = close(project)
            self.assertIn("The setting `jotting` is `later` on this machine, and that cannot be done here: the engine does not find this conversation", out)
            self.assertIn("Nothing was read back from the conversation: go through it as you hold it.", out)
            for spoil, wanted in (
                (lambda: home.keep(NAME, [], "not json\n"), "does not read as a Claude Code conversation"),
                (lambda: project.write("vesta/.state/history.json", "{"), "vesta/.state/history.json does not read"),
            ):
                home.keep(NAME, [BEFORE, DURING])
                spoil()
                out = close(project)
                self.assertIn("What the owner said could not be read back from the conversation:", out)
                self.assertIn(wanted, out)
                self.assertIn("Go through the conversation as you hold it.", out)
                self.assertIn("## 6.", out)
                self.assertNotIn("did not expect", out)
            self.assertEqual(session.id, state.open_ones(project.context().tree)[0].id)

    def test_a_long_task_is_printed_to_its_end_by_the_command_the_sheet_names(self):
        with Project(init=True) as project, Home(project) as home:
            session = later(project, home, [BEFORE])
            many = [said("user", "correction %02d: %s" % (number, "word " * 200), "2026-01-05T09:%02d:00Z" % (number + 1)) for number in range(30)]
            home.keep(NAME, [BEFORE] + many)
            out = close(project)
            self.assertLess(len(out), 30000)
            seen = set(re.findall(r"correction (\d\d):", out))
            command = re.search(r"`(history turns claude-code \S+ --session \S+ --at \d+)`", out)
            self.assertIsNotNone(command)
            arguments = command.group(1).split()
            while True:
                code, out, err = project.run(*arguments)
                self.assertEqual(code, 0, err)
                seen.update(re.findall(r"correction (\d\d):", out))
                following = re.search(r"The next start at `--at (\d+)`", out)
                if not following:
                    break
                arguments[-1] = following.group(1)
            self.assertEqual(len(seen), 30)
            code, out, err = project.run("history", "turns", "claude-code", NAME, "--session", session.id, "--at", "999")
            self.assertEqual(code, 2)

    def test_a_session_that_read_nothing_of_a_conversation_is_refused_its_pieces(self):
        with Project(init=True) as project, Home(project) as home:
            session = later(project, home, [BEFORE])
            home.keep("other", TALK)
            code, out, err = project.run("history", "turns", "claude-code", "other", "--session", session.id)
            self.assertEqual(code, 2)
            self.assertIn("read nothing back from that conversation", err)

    def test_the_conversation_a_command_is_started_from_is_left_out_of_the_list_and_said(self):
        with in_claude(Project(init=True)) as project, Home(project) as home:
            home.keep(NAME, [BEFORE, DURING])
            home.keep("older", TALK)
            code, out, err = project.run("history", "list", "claude-code")
            self.assertEqual(code, 0, err)
            self.assertIn("- `older`", out)
            self.assertNotIn("- `%s`" % NAME, out)
            self.assertIn("Left out: `%s`, the conversation this command was started from." % NAME, out)
            self.assertIn("Opened to find them: 1 of 1 file.", out)
            self.assertNotIn("Not looked at", out)
            project.environ = {}
            self.assertIn("- `%s`" % NAME, project.run("history", "list", "claude-code")[1])

    def test_the_conversation_a_command_is_started_from_is_not_opened_to_be_read_back(self):
        with in_claude(Project(init=True)) as project, Home(project) as home:
            home.keep(NAME, [BEFORE, DURING])
            code, out, err = project.run("walk", "backfill", "--source", "claude-code", "--conversation", NAME)
            self.assertEqual(code, 3, err)
            self.assertIn("is the conversation this command was started from", out)
            self.assertEqual(state.reading_back(project.context().tree), [])
            self.assertEqual(project.run("walk", "backfill", "--source", "claude-code", "--conversation", NAME, "--in", home.folder)[0], 0)

    def test_after_the_report_nothing_is_noted_by_hand_and_with_here_it_is(self):
        with Project(init=True) as project, Home(project) as home:
            session = later(project, home, [BEFORE])
            add_note(project, session)
            project.run("session", "close", "--session", session.id)
            code, out, err = project.run("walk", "close", "--from", "choices", "--session", session.id)
            self.assertEqual(code, 0, err)
            self.assertIn("note nothing: it is read back from this conversation at the next review", out)
            self.assertNotIn("run `jot --steer -`", out)
            choose(project, "jotting", "here")
            out = project.run("walk", "close", "--from", "choices", "--session", session.id)[1]
            self.assertIn("run `jot --steer -`", out)


class Launched(object):
    """Stands in for starting a process that is not waited for: keeps what would have been started.
    For the process that holds a copy of a review, it does what that process would: `does` stands
    for the copy's own work, and `ended` says whether the copy has ended by the time anyone looks."""

    def __init__(self, does=None, fails=None, ended=True, why="ended"):
        self.calls, self.does, self.fails, self.ended, self.why = [], does, fails, ended, why

    def __enter__(self):
        self.before = (aside_command.launch, aside_command.pause, aside_command.WAIT)
        aside_command.launch, aside_command.pause, aside_command.WAIT = self.launch, lambda: None, 1
        return self

    def __exit__(self, *_):
        aside_command.launch, aside_command.pause, aside_command.WAIT = self.before

    def launch(self, command, environ, root):
        if self.fails:
            raise self.fails
        self.calls.append((command, environ, root))
        if aside_command.HOLD not in command:
            return
        if self.does:
            self.does(command, environ)
        if self.ended:
            from kernel.tree import DiskTree
            tree, name = DiskTree(root), command[command.index("--session") + 1]

            def end(fresh):
                if state.copy_of(fresh) is not None and state.copy_of(fresh)["id"] == environ["VESTA_ASIDE"]:
                    fresh.data["copy"]["ended"] = self.why
            state.update(tree, state.named(tree, name), end)


def held(project, session, command, environ):
    """What the process that holds a copy would start: the copy's own command, as the engine builds it."""
    seen = []
    before = aside_command.run_copy
    aside_command.run_copy = lambda argv, env, root, stopped: seen.append((argv, env)) or ""
    try:
        code, out, err = project.run(*command[2:], environ=environ)
    finally:
        aside_command.run_copy = before
    assert code == 0, out + err
    return seen


def hook(project, words="no, never sleep in the fetch path", name=NAME, raw=None):
    sent = raw if raw is not None else json.dumps({"session_id": name, "prompt": words, "cwd": project.root, "hook_event_name": "UserPromptSubmit"})
    return project.run("aside", stdin=io.StringIO(sent))


def report(project, word, token):
    return project.run("aside", word, environ=dict(project.environ, VESTA_ASIDE=token))


class Aside(unittest.TestCase):
    def test_choosing_it_prints_the_entry_the_owner_adds_and_where(self):
        with in_claude(Project(init=True)) as project, Home(project) as home:
            home.keep(NAME, [BEFORE])
            out = choose(project, "jotting", "aside")
            self.assertIn("Add this to `.claude/settings.local.json`", out)
            entry = json.loads(out[out.index("{"):out.rindex("}") + 1])
            command = entry["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
            self.assertEqual(command, '"%s" "%s/vesta/.engine" aside' % (sys.executable.replace("\\", "/"), project.root.replace("\\", "/")))
            self.assertIn("see that it is not committed", out)
            self.assertIn("Until it is there, nothing is noted aside", out)
            self.assertNotIn("settings.local.json", choose(project, "jotting", "later"))

    def test_each_time_the_owner_speaks_a_copy_is_started_for_that_conversation_and_nothing_is_printed(self):
        with Project(init=True) as project, Home(project) as home, Launched() as launched:
            session = later(project, home, [BEFORE], "aside")
            self.assertEqual(hook(project), (0, "", ""))
            ((command, environ, root),) = launched.calls
            self.assertEqual(command[:4], ["claude", "-p", "--resume", NAME])
            self.assertEqual(root, project.root)
            (entry,) = asides.read(project.context().tree)
            self.assertEqual((entry["conversation"], entry["session"], entry["answer"], entry["words"]), (NAME, session.id, "", "no, never sleep in the fetch path"))
            self.assertEqual(environ["VESTA_ASIDE"], entry["id"])
            prompt = command[-1]
            self.assertIn("> no, never sleep in the fetch path", prompt)
            line = 'python3 "%s/vesta/.engine"' % project.root.replace("\\", "/")
            self.assertIn("run exactly `%s aside steer`" % line, prompt)
            self.assertIn("run exactly `%s aside nothing`" % line, prompt)
            self.assertIn("Bash(%s aside *)" % line, command)
            self.assertNotIn("{", prompt)

    def test_the_harness_own_run_never_prints_and_never_fails_whatever_it_is_sent(self):
        with Project(init=True) as project, Home(project) as home, Launched() as launched:
            later(project, home, [BEFORE], "aside")
            for raw in ("", "{", "[]", "null", '{"prompt": 3}', '{"session_id": "../x", "prompt": "hi"}', '{"session_id": "%s", "prompt": "  "}' % NAME, "\x00"):
                self.assertEqual(hook(project, raw=raw), (0, "", ""), raw)
            project.write("vesta/.state/asides.json", "{")
            self.assertEqual(hook(project), (0, "", ""))
            os.remove(project.path("vesta/.state/asides.json"))
            project.write("vesta/.state/settings.json", "{")
            self.assertEqual(hook(project), (0, "", ""))
            self.assertEqual(launched.calls, [])

    def test_no_copy_is_started_where_the_setting_is_another_or_by_a_copy(self):
        with Project(init=True) as project, Home(project) as home, Launched() as launched:
            later(project, home, [BEFORE], "later")
            hook(project)
            choose(project, "jotting", "aside")
            project.run("aside", stdin=io.StringIO(json.dumps({"session_id": NAME, "prompt": "x"})), environ=dict(project.environ, VESTA_ASIDE="abc"))
            project.environ = {}
            project.run("aside", stdin=io.StringIO(json.dumps({"session_id": NAME, "prompt": "said from no harness the engine knows"})))
            self.assertEqual(launched.calls, [])
            self.assertFalse(os.path.exists(project.path("vesta/.state/asides.json")))

    def test_what_the_harness_sends_says_which_harness_it_is_where_the_environment_does_not(self):
        with Project(init=True) as project, Home(project) as home, Launched() as launched:
            later(project, home, [BEFORE], "aside")
            project.environ = {}
            self.assertEqual(hook(project), (0, "", ""))
            ((command, environ, _),) = launched.calls
            self.assertEqual(command[3], NAME)
            self.assertEqual((environ["CLAUDECODE"], environ["CLAUDE_CODE_SESSION_ID"]), ("1", NAME))

    def test_a_copy_reports_once_and_a_correction_lands_in_the_session_of_its_conversation(self):
        with Project(init=True) as project, Home(project) as home, Launched():
            session = later(project, home, [BEFORE], "aside")
            other = project.run("walk", "start", "--ask", "a second agent's task", "--parallel", environ={})
            self.assertEqual(other[0], 0, other[2])
            hook(project, "no, never sleep in the fetch path")
            hook(project, "thanks, looks good")
            first, second = [entry["id"] for entry in asides.read(project.context().tree)]
            code, out, err = report(project, "steer", first)
            self.assertEqual(code, 0, err)
            self.assertIn("Noted in %s as a correction from the owner" % session.id, out)
            (jot,) = state.named(project.context().tree, session.id).jots
            self.assertEqual((jot["steer"], jot["text"]), (True, "no, never sleep in the fetch path"))
            self.assertIn("already reported: noted", report(project, "nothing", first)[1])
            self.assertEqual(len(state.named(project.context().tree, session.id).jots), 1)
            self.assertIn("nothing to note", report(project, "nothing", second)[1])
            self.assertEqual([entry["answer"] for entry in asides.read(project.context().tree)], ["noted", "nothing"])

    def test_a_report_from_no_copy_is_refused_and_notes_nothing(self):
        with Project(init=True) as project, Home(project) as home:
            session = later(project, home, [BEFORE], "aside")
            for word in ("steer", "nothing"):
                for token in ("", "nope"):
                    code, out, err = report(project, word, token)
                    self.assertEqual(code, 3, word)
                    self.assertIn("this command was not started by one", out)
            self.assertEqual(state.named(project.context().tree, session.id).jots, [])
            code, out, err = project.run("aside", "loudly")
            self.assertEqual(code, 2)
            self.assertIn("`aside` takes one of: steer, nothing, or `walk <checkpoint>`", err)

    def test_a_correction_noted_after_the_task_ended_opens_a_session_to_hold_it(self):
        with Project(init=True) as project, Home(project) as home, Launched():
            session = later(project, home, [BEFORE], "aside")
            hook(project)
            project.run("session", "abandon", session.id)
            (entry,) = asides.read(project.context().tree)
            code, out, err = report(project, "steer", entry["id"])
            self.assertEqual(code, 0, err)
            self.assertIn("which was opened late to hold it", out)
            self.assertEqual(len(state.open_ones(project.context().tree)[0].jots), 1)

    def test_the_review_trusts_a_copy_only_for_the_words_it_was_started_for(self):
        with Project(init=True) as project, Home(project) as home, Launched():
            later(project, home, [BEFORE], "aside")
            second = said("user", "and keep the public names as they are", "2026-01-05T09:12:00Z")
            home.keep(NAME, [BEFORE, DURING, second])
            out = close(project)
            self.assertIn("No copy of the conversation was started in this task", out)
            self.assertIn("`setting jotting aside` prints it", out)
            self.assertIn("> no, never sleep in the fetch path", out)
            project.clock.advance(seconds=60)
            hook(project)
            out = close(project)
            self.assertIn("A copy of the conversation was started 1 time, and 0 reported back. Of the 2 things the owner said, 2 had no copy that reported", out)
            (entry,) = asides.read(project.context().tree)
            report(project, "steer", entry["id"])
            out = close(project)
            # The words no copy was started for are still printed: nothing the owner said goes unread.
            self.assertIn("Of the 2 things the owner said, 1 had no copy that reported, and is read back here", out)
            self.assertIn("> and keep the public names as they are", out)
            self.assertNotIn("> no, never sleep", out)
            self.assertIn("no, never sleep in the fetch path (from jot)", out)
            hook(project, "and keep the public names as they are")
            report(project, "nothing", asides.read(project.context().tree)[-1]["id"])
            out = close(project)
            self.assertIn("Noted aside: the owner said 2 things in this task, a copy of the conversation was started for each, and each reported back. 1 noted a correction", out)
            self.assertNotIn("> and keep the public names", out)

    def test_several_reports_of_one_copy_at_once_note_the_correction_once(self):
        with Project(init=True) as project, Home(project) as home, Launched():
            session = later(project, home, [BEFORE], "aside")
            hook(project)
            (entry,) = asides.read(project.context().tree)
            import threading
            found = []
            threads = [threading.Thread(target=lambda: found.append(report(project, "steer", entry["id"]))) for _ in range(6)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(len(state.named(project.context().tree, session.id).jots), 1, found)
            self.assertEqual(len([1 for _, out, _ in found if "Noted in" in out]), 1)

    def test_a_correction_that_cannot_be_noted_is_written_down_as_failed_and_read_back(self):
        with Project(init=True) as project, Home(project) as home, Launched():
            session = later(project, home, [BEFORE], "aside")
            hook(project)
            project.run("session", "abandon", session.id)
            for _ in range(2):
                self.assertEqual(project.run("walk", "start", "--ask", "another agent's task", "--parallel", environ={})[0], 0)
            (entry,) = asides.read(project.context().tree)
            code, out, err = report(project, "steer", entry["id"])
            self.assertEqual(code, 0, err)
            self.assertIn("The correction could not be noted (2 sessions are open", out)
            self.assertIn("failed: ", asides.read(project.context().tree)[0]["answer"])

    def test_a_note_opened_late_by_a_copy_belongs_to_the_owners_conversation_and_not_the_copys(self):
        with Project(init=True) as project, Home(project) as home, Launched():
            session = later(project, home, [BEFORE], "aside")
            hook(project)
            project.run("session", "abandon", session.id)
            (entry,) = asides.read(project.context().tree)
            project.run("aside", "steer", environ=dict(project.environ, VESTA_ASIDE=entry["id"], CLAUDE_CODE_SESSION_ID="the-copy"))
            self.assertEqual(state.open_ones(project.context().tree)[0].data["conversation"], {"harness": "claude-code", "name": NAME})

    def test_a_copy_that_cannot_be_started_is_written_down_and_doctor_says_so(self):
        with Project(init=True) as project, Home(project) as home, Launched(fails=OSError(2, "No such file or directory: 'claude'")):
            later(project, home, [BEFORE], "aside")
            home.keep(NAME, [BEFORE, DURING])
            self.assertEqual(hook(project), (0, "", ""))
            (entry,) = asides.read(project.context().tree)
            self.assertIn("failed: ", entry["answer"])
            code, out, err = project.run("doctor")
            self.assertEqual(code, 0, err)
            self.assertIn("Copies of a conversation started aside: 1 kept on record, of which 1 did not report back; the last of those: failed:", out)
            out = close(project)
            self.assertIn("A copy of the conversation was started 1 time, and 0 reported back.", out)
            self.assertIn("> no, never sleep in the fetch path", out)

    def test_a_record_of_copies_that_does_not_read_is_named_and_the_review_reads_back(self):
        with Project(init=True) as project, Home(project) as home:
            later(project, home, [BEFORE], "aside")
            home.keep(NAME, [BEFORE, DURING])
            for bad in ("{", "[]", '{"asides": [{"id": 1}]}', "\xff"):
                project.write("vesta/.state/asides.json", bad)
                out = close(project)
                self.assertIn("vesta/.state/asides.json does not read", out)
                self.assertIn("> no, never sleep in the fetch path", out)
                code, out, err = project.run("doctor")
                self.assertEqual(code, 0, err)
                self.assertIn("- Copies of a conversation started aside: vesta/.state/asides.json does not read", out)


@unittest.skipIf(os.name == "nt", "the stand-in for the harness's program is a shell script")
class ThroughTheBuiltCopy(unittest.TestCase):
    def test_a_copy_started_by_the_real_command_notes_the_correction_from_a_path_with_a_space(self):
        with Project(init=True) as project:
            root = os.path.join(project.root, "my project")
            os.makedirs(os.path.join(root, "vesta"))
            shutil.copytree(BUILT, os.path.join(root, "vesta", ".engine"))
            home = Home(project, root)
            try:
                home.keep(NAME, [BEFORE])
                tools = os.path.join(project.root, "tools")
                os.makedirs(tools)
                program = os.path.join(tools, "claude")
                # Stands in for the harness's program: it does what the copy is told to do for a correction.
                support.write(program, "#!/bin/sh\nexec \"%s\" \"%s\" aside steer\n" % (sys.executable, os.path.join(root, "vesta", ".engine")))
                os.chmod(program, os.stat(program).st_mode | stat.S_IEXEC)
                environ = dict(os.environ, PATH=tools + os.pathsep + os.environ.get("PATH", ""), **IN_CLAUDE)
                environ.pop("VESTA_ASIDE", None)
                engine = [sys.executable, os.path.join(root, "vesta", ".engine")]

                def run(*arguments, **more):
                    found = subprocess.run(engine + list(arguments), capture_output=True, env=environ, **more)
                    return found.returncode, found.stdout.decode("utf-8"), found.stderr.decode("utf-8")

                self.assertEqual(run("init")[0], 0)
                self.assertEqual(run("setting", "jotting", "aside")[0], 0)
                self.assertEqual(run("walk", "start", "--ask", "add a retry")[0], 0)
                sent = json.dumps({"session_id": NAME, "prompt": "no — never sleep in the fetch path"}).encode("utf-8")
                self.assertEqual(run("aside", input=sent), (0, "", ""))
                path = os.path.join(root, "vesta", ".state", "asides.json")
                for _ in range(100):
                    if json.loads(support.read(path))["asides"][0]["answer"]:
                        break
                    time.sleep(0.1)
                self.assertEqual(json.loads(support.read(path))["asides"][0]["answer"], "noted")
                code, out, err = run("session", "show")
                self.assertIn("[steer] no — never sleep in the fetch path", out)
                code, out, err = run("check")
                self.assertEqual(code, 0, out + err)
            finally:
                home.__exit__()


@unittest.skipIf(os.name == "nt", "the stand-in for the harness's program is a shell script")
class ReviewThroughTheBuiltCopy(unittest.TestCase):
    """The real commands, as separate processes, with a stand-in for the harness's program."""

    def setUp(self):
        self.project = Project(init=True)
        self.root = os.path.join(self.project.root, "my project")
        os.makedirs(os.path.join(self.root, "vesta"))
        shutil.copytree(BUILT, os.path.join(self.root, "vesta", ".engine"))
        self.home = Home(self.project, self.root)
        self.home.keep(NAME, [BEFORE])
        self.tools = os.path.join(self.project.root, "tools")
        os.makedirs(self.tools)
        self.log = os.path.join(self.project.root, "started.log")
        self.engine = [sys.executable, os.path.join(self.root, "vesta", ".engine")]
        self.environ = dict(os.environ, PATH=self.tools + os.pathsep + os.environ.get("PATH", ""), **IN_CLAUDE)
        self.environ.pop("VESTA_ASIDE", None)
        self.environ.pop("VESTA_CONVERSATION", None)
        for arguments in (("init",), ("setting", "review", "aside"), ("walk", "start", "--ask", "add a retry")):
            self.assertEqual(self.run_engine(*arguments)[0], 0, arguments)

    def tearDown(self):
        self.home.__exit__()
        self.project.__exit__()

    def program(self, body):
        path = os.path.join(self.tools, "claude")
        support.write(path, "#!/bin/sh\necho started >> \"%s\"\n%s\n" % (self.log, body))
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)

    def run_engine(self, *arguments):
        found = subprocess.run(self.engine + list(arguments), capture_output=True, env=self.environ)
        return found.returncode, found.stdout.decode("utf-8"), found.stderr.decode("utf-8")

    def copy(self):
        (leaf,) = [leaf for leaf in os.listdir(os.path.join(self.root, "vesta", ".state", "sessions")) if leaf.endswith(".json")]
        return json.loads(support.read(os.path.join(self.root, "vesta", ".state", "sessions", leaf))).get("copy")

    def test_a_copy_that_closes_the_session_is_waited_for_and_the_next_part_is_named(self):
        self.program('exec "%s" "%s" session close' % (sys.executable, self.engine[1]))
        code, out, err = self.run_engine("aside", "walk", "close")
        self.assertEqual(code, 0, err)
        self.assertIn("The copy finished the part", out)
        self.assertIn("walk close --from choices", out)
        self.assertEqual(support.read(self.log).count("started"), 1)

    def test_a_copy_at_work_is_ended_with_everything_it_started_and_never_by_a_number_from_a_file(self):
        child = os.path.join(self.project.root, "child.pid")
        self.program('sleep 300 &\necho $! > "%s"\nwait' % child)
        process = subprocess.Popen(self.engine + ["aside", "walk", "close"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.environ)
        for _ in range(100):
            if os.path.exists(child) and support.read(child).strip():
                break
            time.sleep(0.1)
        pid = int(support.read(child))
        self.assertNotIn("pid", self.copy())
        process.kill()  # the waiting command goes away; the copy goes on
        process.communicate()
        os.kill(pid, 0)
        code, out, err = self.run_engine("aside", "walk", "close", "--stop")
        self.assertEqual(code, 0, err)
        self.assertIn("is being stopped", out)
        gone = False
        for _ in range(100):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                gone = True
                break
            time.sleep(0.1)
        self.assertTrue(gone, "what the copy started outlived the copy")
        self.assertIsNone(self.copy())
        self.assertEqual(self.run_engine("walk", "close", "--here")[0], 0)

    def test_several_commands_at_once_start_one_copy(self):
        self.program("sleep 2")
        running = [subprocess.Popen(self.engine + ["aside", "walk", "close"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.environ) for _ in range(5)]
        for process in running:
            process.communicate()
        time.sleep(0.5)
        self.assertEqual(support.read(self.log).count("started"), 1)


def carried_out(project, session, closes=True):
    """What a copy does for the first part of a review: a note, and the session closed."""
    def does(command, environ):
        add_note(project, session, body="\"never sleep in the fetch path\"", anchor="src/fetch.py", moment="work")
        if closes:
            assert project.run("session", "close", "--session", session.id)[0] == 0
        return ""
    return does


class ReviewAside(unittest.TestCase):
    def test_the_first_part_is_not_printed_where_a_copy_carries_it_out_and_here_prints_it(self):
        with Project(init=True) as project, Home(project) as home:
            session = later(project, home, [BEFORE], "here")
            choose(project, "review", "aside")
            out = close(project)
            self.assertIn("The first part of this walk is carried out aside", out)
            self.assertNotIn("## 1.", out)
            line = 'python3 "%s/vesta/.engine"' % project.root.replace("\\", "/")
            self.assertIn("Run `%s aside walk close --session %s`" % (line, session.id), out)
            self.assertIn("run `walk close --here --session %s`" % session.id, out)
            self.assertIn("aside walk close --short --session", close(project, "--short"))
            self.assertIn("## 1. Bundle", close(project, "--here"))
            choose(project, "review", "here")
            self.assertIn("## 1. Bundle", close(project))

    def test_the_copy_is_told_which_sheet_to_carry_out_and_the_result_names_the_next_part(self):
        with Project(init=True) as project, Home(project) as home:
            session = later(project, home, [BEFORE], "here")
            choose(project, "review", "aside")
            with Launched(ended=False) as launched:
                project.run("aside", "walk", "close", "--session", session.id)
            ((holder, environ, _),) = launched.calls
            self.assertEqual(holder[2:5], ["aside", "hold", "close"])
            self.assertEqual(environ["VESTA_CONVERSATION"], NAME)
            self.assertEqual(environ["VESTA_ASIDE"], state.copy_of(state.named(project.context().tree, session.id))["id"])
            ((command, _),) = held(project, session, holder, environ)
            line = 'python3 "%s/vesta/.engine"' % project.root.replace("\\", "/")
            self.assertEqual(command[:5], ["claude", "-p", "--resume", NAME, "--fork-session"])
            self.assertIn("Run `%s walk close --here --session %s`" % (line, session.id), command[-1])
            self.assertIn("Bash(%s *)" % line, command)
            self.assertIn("Read", command)
            self.assertEqual(state.copy_of(state.named(project.context().tree, session.id))["ended"], "ended")
            carried_out(project, session)(None, None)
            code, out, err = project.run("aside", "walk", "close", "--session", session.id)
            self.assertEqual(code, 0, err)
            self.assertIn("Notes the copy wrote: 1", out)
            self.assertIn("The copy finished the part, and %s is closed." % session.id, out)
            following = re.search(r"`(walk close --from \S+ --session \S+)`", out).group(1)
            with Launched() as launched:
                again = project.run("aside", "walk", "close", "--session", session.id)[1]  # run once more: it still says what comes next
            self.assertEqual(launched.calls, [])
            self.assertIn("the part is done with", again)
            self.assertIn(following, again)
            code, out, err = project.run(*following.split())
            self.assertEqual(code, 0, err)
            self.assertIn("The walk is complete", out)
            self.assertEqual(project.run("check")[0], 0)

    def test_the_process_that_holds_a_copy_does_nothing_for_anyone_but_its_own_copy(self):
        with Project(init=True) as project, Home(project) as home, Launched(ended=False) as launched:
            session = later(project, home, [BEFORE], "here")
            choose(project, "review", "aside")
            project.run("aside", "walk", "close")
            ((holder, environ, _),) = launched.calls
            for other in (dict(environ, VESTA_ASIDE="another"), dict((key, value) for key, value in environ.items() if key != "VESTA_ASIDE"), {}):
                self.assertEqual(held(project, session, holder, other), [])
            self.assertNotIn("ended", state.copy_of(state.named(project.context().tree, session.id)))

    def test_a_copy_that_ends_without_finishing_leaves_the_part_to_be_carried_out_here(self):
        with Project(init=True) as project, Home(project) as home:
            session = later(project, home, [BEFORE], "here")
            choose(project, "review", "aside")
            for why, wanted in (("ended", "it ended before the session was closed"), ("it could not be started (no such program)", "it could not be started (no such program)"),
                                ("it was stopped after 15 minutes", "it was stopped after 15 minutes")):
                with Launched(does=carried_out(project, session, closes=False), why=why):
                    code, out, err = project.run("aside", "walk", "close")
                self.assertEqual(code, 0, err)
                self.assertIn("The copy did not finish the part: %s." % wanted, out)
                self.assertIn("`walk close --here --session %s` prints the part to carry out here." % session.id, out)
                self.assertNotIn("--from", out)
                self.assertIsNone(state.copy_of(state.named(project.context().tree, session.id)))
            self.assertIn("## 1. Bundle", close(project, "--here"))
            with Launched(fails=OSError(2, "No such file or directory")):
                out = project.run("aside", "walk", "close")[1]
            self.assertIn("The copy could not be started", out)
            self.assertIn("## 1. Bundle", close(project, "--here"))

    def test_a_copy_still_at_work_is_waited_for_again_and_no_step_of_its_part_is_printed_here(self):
        with Project(init=True) as project, Home(project) as home, Launched(ended=False) as launched:
            session = later(project, home, [BEFORE], "here")
            choose(project, "review", "aside")
            for _ in range(2):
                code, out, err = project.run("aside", "walk", "close", "--session", session.id)
                self.assertEqual(code, 0, err)
                self.assertIn("The copy is still at work; it was started 2026-01-05T09:00:00Z.", out)
                self.assertIn("Run `aside walk close --session %s` again" % session.id, out)
            self.assertEqual(len(launched.calls), 1)  # the second run waits for the same copy
            for arguments in (("--here",), ("--from", "bundle"), ("--from", "steers"), ("--from", "mint"), ("--short", "--from", "steers")):
                code, out, err = project.run("walk", "close", *arguments)
                self.assertEqual(code, 3, arguments)
                self.assertIn("carrying it out here as well would write its notes twice", out)
                self.assertIn("`aside walk close --stop --session %s` ends it" % session.id, out)
                self.assertNotIn("## ", out)
            self.assertEqual(project.run("walk", "close", "--from", "choices")[0], 0)  # the part put to the owner is no part of the copy's
            self.assertIn("aside walk close --session", close(project))  # without `--here` it points at the copy again
            project.clock.advance(seconds=17 * 60)
            out = project.run("aside", "walk", "close")[1]
            self.assertIn("The copy did not finish the part: nothing was heard from it 16 minutes after it was started.", out)
            self.assertIn("## 1. Bundle", close(project, "--here"))

    def test_a_copy_is_ended_by_name_and_the_part_is_then_printed_here(self):
        with Project(init=True) as project, Home(project) as home, Launched(ended=False) as launched:
            session = later(project, home, [BEFORE], "here")
            choose(project, "review", "aside")
            self.assertIn("so nothing was stopped", project.run("aside", "walk", "close", "--stop")[1])
            project.run("aside", "walk", "close")
            ((holder, environ, _),) = launched.calls
            out = project.run("aside", "walk", "close", "--stop")[1]
            self.assertIn("is being stopped. What it wrote stays.", out)
            self.assertIsNone(state.copy_of(state.named(project.context().tree, session.id)))
            self.assertEqual(held(project, session, holder, environ), [])  # the holder finds its record gone, which is how it learns to stop
            self.assertIn("## 1. Bundle", close(project, "--here"))

    def test_several_runs_at_once_start_one_copy(self):
        import threading
        with Project(init=True) as project, Home(project) as home, Launched(ended=False) as launched:
            session = later(project, home, [BEFORE], "here")
            choose(project, "review", "aside")
            threads = [threading.Thread(target=lambda: project.run("aside", "walk", "close", "--session", session.id)) for _ in range(6)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(len(launched.calls), 1)

    def test_what_a_session_file_holds_under_the_copys_key_that_does_not_read_is_no_copy_to_every_command(self):
        with Project(init=True) as project, Home(project) as home, Launched(ended=False) as launched:
            session = later(project, home, [BEFORE], "here")
            choose(project, "review", "aside")
            for bad in ("x", 7, [], {"pid": 4242, "started": "x", "minted": 0}, {"id": "", "started": "x", "minted": 0},
                        {"id": "a", "started": "x", "minted": -1}, {"id": "a", "started": "x", "minted": True}, {"id": "a", "started": 3, "minted": 0}):
                path = "vesta/.state/sessions/%s.json" % session.id
                data = json.loads(project.read(path))
                data["copy"] = bad
                project.write(path, json.dumps(data))
                self.assertIn("## 1. Bundle", close(project, "--here"))
                self.assertIn("so nothing was stopped", project.run("aside", "walk", "close", "--stop")[1])
                self.assertNotIn("did not expect", "".join(project.run("doctor")[1:]))

    def test_what_cannot_be_carried_out_aside_is_refused_before_a_copy_is_started(self):
        with Project(init=True) as project, Home(project) as home, Launched() as launched:
            session = later(project, home, [BEFORE], "here")
            for arguments, code, wanted in (
                (("aside", "walk"), 2, "takes one of the walks a copy may carry out the first part of: close"),
                (("aside", "walk", "start"), 2, "takes one of the walks"),
                (("aside", "walk", "learn"), 2, "takes one of the walks"),
                (("aside", "walk", "close", "--session", "S-00000000-0000"), 2, "is not a session of this project"),
                (("aside", "walk", "close"), 3, "the setting `review` is not `aside` here"),
            ):
                found = project.run(*arguments)
                self.assertEqual(found[0], code, arguments)
                self.assertIn(wanted, found[1] + found[2])
            choose(project, "review", "aside")
            found = project.run("aside", "walk", "close", environ=dict(project.environ, VESTA_ASIDE="walk"))
            self.assertEqual(found[0], 3)
            self.assertIn("a copy starts no copy", found[1])
            project.environ = {}
            found = project.run("aside", "walk", "close")
            self.assertIn("in effect: `here`, because", found[1])
            in_claude(project)
            project.run("session", "abandon", session.id)
            found = project.run("aside", "walk", "close", "--session", session.id)
            self.assertEqual(found[0], 0)
            self.assertIn("is abandoned: the part is done with, and no copy was started. It was left unfinished", found[1])
            self.assertNotIn("--from", found[1])
            self.assertEqual(launched.calls, [])

    def test_a_review_opened_without_a_start_tells_the_copy_which_conversation_it_reads(self):
        with in_claude(Project(init=True)) as project, Home(project) as home:
            choose(project, "review", "aside")
            choose(project, "jotting", "later")
            home.keep(NAME, [BEFORE, DURING])
            out = close(project, "--ask", "what was done")
            self.assertIn("carried out aside", out)
            session = state.open_ones(project.context().tree)[0]
            seen = []

            def does(command, environ):
                # The copy's own conversation has another name and no file: the sheet still reads the original.
                seen.append(project.run("walk", "close", "--here", "--session", session.id, environ=dict(environ, CLAUDE_CODE_SESSION_ID="the-copy"))[1])
                return ""
            with Launched(does=does):
                project.run("aside", "walk", "close")
            self.assertIn("> no, never sleep in the fetch path", seen[0])


class HookThroughTheBuiltCopy(unittest.TestCase):
    def test_the_harness_own_run_prints_nothing_and_ends_well_even_over_a_project_that_does_not_read(self):
        with Project(init=True) as project:
            root = os.path.join(project.root, "my project")
            os.makedirs(os.path.join(root, "vesta"))
            shutil.copytree(BUILT, os.path.join(root, "vesta", ".engine"))
            engine = [sys.executable, os.path.join(root, "vesta", ".engine")]
            environ = dict(os.environ, **IN_CLAUDE)
            self.assertEqual(subprocess.run(engine + ["init"], capture_output=True, env=environ).returncode, 0)
            sent = json.dumps({"session_id": NAME, "prompt": "hi", "hook_event_name": "UserPromptSubmit"}).encode("utf-8")

            def hooked():
                found = subprocess.run(engine + ["aside"], capture_output=True, env=environ, input=sent)
                return found.returncode, found.stdout, found.stderr

            self.assertEqual(hooked(), (0, b"", b""))
            support.write(os.path.join(root, "vesta", ".state", "journal.json"), "{")
            self.assertEqual(hooked(), (0, b"", b""))
            support.write(os.path.join(root, "vesta", "vesta.yml"), "schema: [\n")
            self.assertEqual(hooked(), (0, b"", b""))
            os.remove(os.path.join(root, "vesta", "vesta.yml"))
            self.assertEqual(hooked(), (0, b"", b""))
            os.remove(os.path.join(root, "vesta", ".engine", "session", "asides.py"))
            self.assertEqual(hooked(), (0, b"", b""))
            # Any other run of the command still says what is wrong.
            found = subprocess.run(engine + ["aside", "nothing"], capture_output=True, env=environ)
            self.assertNotEqual(found.returncode, 0)


class Notes(unittest.TestCase):
    """Every walk that writes notes is held to the same words, and the engine says which walk wrote one."""

    def card(self, out):
        start = out.index("How to write one, from `vesta/observations/SCHEMA.md`")
        return out[start:out.index("`obs add", start)]

    def test_the_review_and_the_reading_back_print_the_same_card_from_the_projects_own_file(self):
        with Project(init=True) as project, Home(project) as home:
            home.keep("one", TALK)
            start(project)
            review = close(project)
            code, back, err = project.run("walk", "backfill", "--source", "claude-code", "--conversation", "one")
            self.assertEqual(code, 0, err)
            self.assertEqual(self.card(review), self.card(back))
            schema = project.read("vesta/observations/SCHEMA.md")
            for wanted in ("### Title and body", "### Do and Don't", "It is not an instruction and not a fix",
                           "Write both for a reader who was not there", "Quote nothing that reads as a password"):
                self.assertIn(wanted, self.card(review))
            self.assertIn("The title names what was noticed, as a thing that happened", schema)
            for out in (review, back):
                self.assertIn("**Do:** Write every prepared observation as the sections printed above say", out)
                self.assertIn("rewrite one that states a fix", out)
            # No section of either sheet says in its own words how the body of a correction is written.
            for gone in ("the owner's words quoted", "closely paraphrased", "End the body with"):
                self.assertNotIn(gone, review + back)
            self.assertIn("--session", back[back.index("**Do:** Write every"):])
            self.assertNotIn("with `--session", review)

    def test_a_project_whose_file_lacks_the_sections_is_told_so_and_pointed_at_the_file(self):
        with Project(init=True) as project:
            schema = project.read("vesta/observations/SCHEMA.md")
            project.write("vesta/observations/SCHEMA.md", schema.replace("## Title and body", "## Titles"))
            project.run("adopt", "vesta/observations/SCHEMA.md")
            start(project)
            out = close(project)
            self.assertIn("`vesta/observations/SCHEMA.md` has no section *Title and body* to print here: read the file", out)
            self.assertIn("### Do and Don't", out)

    def test_the_engine_writes_which_walk_wrote_a_note_and_nobody_else_may(self):
        with Project(init=True) as project, Home(project) as home:
            home.keep("one", TALK)
            _, session = start(project)
            add_note(project, session, anchor="src/fetch.py")
            project.run("walk", "backfill", "--source", "claude-code", "--conversation", "one")
            (reading,) = state.reading_back(project.context().tree)
            add_note(project, reading, title="A second thing")
            sources = sorted(re.search(r"^source: (.*)$", project.read(path), re.M).group(1) for path in notes(project))
            self.assertEqual(sources, ["read-back", "review"])
            code, out, err = project.run("obs", "add", "--session", session.id, stdin=io.StringIO(json.dumps([note(source="read-back")])))
            self.assertEqual(code, 3, out + err)
            self.assertIn("`source` is not a key of an item", out)
            self.assertEqual(project.run("check")[0], 0)

    def test_a_store_without_the_field_or_with_another_meaning_for_it_is_left_alone(self):
        with Project(init=True) as project:
            schema = project.read("vesta/observations/SCHEMA.md")
            for changed in (schema.replace("  - name: source\n    type: enum\n    values: [review, read-back]\n", ""),
                            schema.replace("values: [review, read-back]", "values: [desk, field]")):
                self.assertNotEqual(changed, schema)
                project.write("vesta/observations/SCHEMA.md", changed)
                project.run("adopt", "vesta/observations/SCHEMA.md")
                _, session = start(project)
                item = note(anchor="src/fetch.py")
                code, out, err = project.run("obs", "add", "--session", session.id, stdin=io.StringIO(json.dumps([item])))
                self.assertEqual(code, 0, out + err)
                self.assertNotIn("source: review", project.read(notes(project)[-1]))
                project.run("session", "abandon", session.id)

    def test_the_reading_back_says_the_engine_records_it_only_where_the_store_has_the_field(self):
        with Project(init=True) as project, Home(project) as home:
            home.keep("one", TALK)
            home.keep("two", [said("user", "never log the token", "2026-01-03T10:00:00Z")])
            line = "The engine records that the observation was read back"
            self.assertIn(line, project.run("walk", "backfill", "--source", "claude-code", "--conversation", "one")[1])
            schema = project.read("vesta/observations/SCHEMA.md")
            project.write("vesta/observations/SCHEMA.md", schema.replace("  - name: source\n    type: enum\n    values: [review, read-back]\n", ""))
            project.run("adopt", "vesta/observations/SCHEMA.md")
            code, out, err = project.run("walk", "backfill", "--source", "claude-code", "--conversation", "two")
            self.assertEqual(code, 0, err)
            self.assertNotIn(line, out)
            self.assertNotIn("{recorded}", out)

    def test_no_section_and_no_skill_says_in_its_own_words_how_a_note_is_written(self):
        for name in ("mint", "steers", "earlier"):
            text = " ".join(instruction.read(name).split())
            for gone in ("no fix", "two sentences", "quoted or closely paraphrased", "password"):
                self.assertNotIn(gone, text, name)
        for name in ("vesta-backfill", "vesta-insight"):
            text = " ".join(support.read(os.path.join(support.REPO, "skills", name, "SKILL.md")).split())
            for gone in ("two sentences at most", "don't put the fix in it"):
                self.assertNotIn(gone, text, name)
        card = support.read(os.path.join(support.ENGINE, "templates", "vesta", "observations", "SCHEMA.md"))
        self.assertIn("The title names what the work did, not the rule", " ".join(card.split()))

    def test_a_note_written_before_the_field_was_there_draws_no_finding(self):
        with Project(init=True) as project:
            _, session = start(project)
            add_note(project, session, anchor="src/fetch.py")
            (path,) = notes(project)
            project.write(path, project.read(path).replace("source: review\n", ""))
            self.assertEqual(project.check(), [])
            project.write(path, project.read(path).replace("via: owner-steer\n", ""))
            self.assertNotEqual(project.check(), [])  # a field the schema requires is still asked for


def config(project, *arguments):
    return project.run("config", *arguments)


class Config(unittest.TestCase):
    def test_what_can_be_changed_is_listed_with_how_it_stands_and_what_it_takes(self):
        with Project(init=True) as project:
            code, out, err = config(project)
            self.assertEqual(code, 0, err)
            self.assertLess(out.index("## On this machine"), out.index("## For the project"))
            for name in manifest.SETTINGS:
                self.assertIn("- `%s`: " % name, out)
            for wanted in ("- `engagement`: how much the agent asks, tells and offers. Now `standard`. Takes one of quiet, standard, active.",
                           "- `reminders.learn.open-observations`:", "- `stores.decisions.label.prefix`:", "- `checkpoints.close.short`:",
                           "- `checkpoints.start.short`: the steps of the walk's short form. Now not set.",
                           "`propose config --target vesta.yml --source owner`"):
                self.assertIn(wanted, out)
            self.assertLess(len(out), 12000)

    def test_every_key_it_offers_is_one_the_configuration_has_and_set_takes_it(self):
        from model import config as configuration
        with Project(init=True) as project:
            data = project.context().config.data
            values = {configuration.INT: "7", configuration.BOOL: "false", configuration.TEXT: "auto"}
            for key, means, shape in configuration.offered(data):
                self.assertTrue(means)
                text = values.get(shape) if isinstance(shape, str) else None
                if key == "owner":
                    text = "A. Owner"
                if key.endswith("label.prefix"):
                    continue  # a prefix must differ from every other store's; held by the next test
                if text is None:
                    text = shape[0] if isinstance(shape, tuple) else "bundle, marks, steers, mint" if key == "checkpoints.close.short" else None
                if text is None:
                    continue
                code, out, err = config(project, "set", key, text)
                self.assertEqual(code, 0, (key, out, err))
                self.assertRegex(out, r"(Drafted P-\d+|already, so no proposal was drafted)")

    def test_a_change_is_drafted_whole_and_takes_effect_only_once_it_is_applied(self):
        with Project(init=True) as project:
            code, out, err = config(project, "set", "engagement", "quiet")
            self.assertEqual(code, 0, err)
            label = re.search(r"Drafted (P-\d+): `engagement` would go from `standard` to `quiet`", out).group(1)
            self.assertIn("On a yes that names it, run `apply %s`" % label, out)
            self.assertEqual(project.context().config.engagement, "standard")
            code, shown, err = project.run("proposals", label)
            self.assertEqual(code, 0, err)
            self.assertIn("source: owner", shown)
            self.assertIn("It reads, and could be applied once the owner approves it.", shown)
            self.assertNotIn("<fill:", shown)
            self.assertEqual(project.run("apply", label)[0], 0)
            self.assertEqual(project.context().config.engagement, "quiet")
            self.assertEqual(project.run("check")[0], 0)
            self.assertIn("`engagement` is `quiet` already, so no proposal was drafted.", config(project, "set", "engagement", "quiet")[1])
            code, out, err = config(project, "set", "stores.decisions.label.prefix", "DEC")
            label = re.search(r"Drafted (P-\d+)", out).group(1)
            self.assertEqual(project.run("reject", label, "--reason", "not now")[0], 0)
            self.assertEqual(project.context().config.stores["decisions"].prefix, "D")

    def test_what_cannot_be_set_is_refused_by_name_and_nothing_is_drafted(self):
        with Project(init=True) as project:
            for arguments, code, wanted in (
                (("set", "schema", "2"), 2, "`schema` is not a key `config set` changes"),
                (("set", "pointer-file", "AGENTS.md"), 2, "is not a key `config set` changes"),
                (("set", "stores.nope.label.prefix", "X"), 2, "is not a key `config set` changes"),
                (("set", "engagement", "loud"), 2, "`engagement` takes one of quiet, standard, active; `loud` is not that"),
                (("set", "reminders.learn.open-observations", "forty"), 2, "takes a whole number, zero or more"),
                (("set", "reminders.learn.open-observations", "-3"), 2, "takes a whole number, zero or more"),
                (("set", "reminders.learn.enabled", "yes"), 2, "takes true or false"),
                (("set", "owner", "a\nb"), 2, "takes one line of text"),
                (("set", "changes.ignore", "a b; rm"), 2, "takes a list of names with commas between them"),
                (("set", "engagement"), 2, "takes nothing, or `set <key> <value>`"),
                (("show",), 2, "takes nothing, or `set <key> <value>`"),
                (("set", "checkpoints.close.short", "bundle, nope"), 3, "names the step `nope`, which this engine does not have"),
                (("set", "stores.decisions.label.prefix", "O"), 3, "which is also the prefix of the store `decisions`"),
                (("set", "adapters.changes", "svn"), 3, "names the change source `svn`, which this engine does not have"),
            ):
                found = config(project, *arguments)
                self.assertEqual(found[0], code, arguments)
                self.assertIn(wanted, found[1] + found[2])
                self.assertNotIn("did not expect", found[1] + found[2])
            self.assertEqual([path for path in project.files("vesta/proposals") if "P-" in path], [])
            self.assertEqual(project.run("check")[0], 0)

    def test_a_file_edited_by_hand_into_another_shape_is_refused_by_the_key_and_reaches_no_catch_all(self):
        with Project(init=True) as project:
            text = project.read("vesta/vesta.yml")
            for spoiled, key in ((re.sub(r"reminders:\n(  .*\n)+", "reminders: 5\n", text), "reminders.learn.enabled"),
                                 (text.replace("label:\n      prefix: D\n      digits: 3", "label: 5"), "stores.decisions.label.prefix")):
                self.assertNotEqual(spoiled, text)
                project.write("vesta/vesta.yml", spoiled)
                code, out, err = config(project, "set", key, "false" if "enabled" in key else "DEC")
                self.assertEqual(code, 2, out + err)
                self.assertIn("is not a mapping, so `%s` cannot be set under it" % key, err)
                self.assertNotIn("did not expect", out + err)
                self.assertEqual(config(project)[0], 0)

    def test_a_number_is_plain_digits_and_a_name_is_not_a_lone_dash(self):
        with Project(init=True) as project:
            for value in ("\u0663", "\u00b2", "1e3", "+3", " 3 4", "0x10"):
                code, out, err = config(project, "set", "reminders.unreviewed.sessions", value)
                self.assertEqual(code, 2, value)
                self.assertIn("takes a whole number, zero or more", err)
            code, out, err = config(project, "set", "owner", "-")
            self.assertEqual(code, 2)
            self.assertIn("not `-` alone", err)
            code, out, err = config(project, "set", "owner", "A. Owner")
            self.assertEqual(code, 0, err)
            label = re.search(r"Drafted (P-\d+)", out).group(1)
            project.run("apply", label)
            out = config(project, "set", "owner", "")[1]
            self.assertIn("would go from `A. Owner` to `(empty)`", out)
            self.assertEqual([path for path in project.files("vesta/proposals") if "P-" in path and "(empty)" not in project.read(path)], [])

    def test_a_second_proposal_for_one_key_is_not_drafted_twice_and_a_rival_is_named(self):
        with Project(init=True) as project:
            first = re.search(r"Drafted (P-\d+)", config(project, "set", "engagement", "quiet")[1]).group(1)
            out = config(project, "set", "engagement", "quiet")[1]
            self.assertIn("%s already proposes `engagement` as `quiet` and is waiting for the owner, so no second proposal was drafted." % first, out)
            out = config(project, "set", "engagement", "active")[1]
            second = re.search(r"Drafted (P-\d+)", out).group(1)
            self.assertIn("%s is also waiting and would set `engagement` to `quiet`. Of two that are applied, the one applied last stands" % first, out)
            self.assertIn("It was `standard` when this was drafted.", project.read("vesta/proposals/%s.md" % second))
            for order in ((first, second), ):
                for label in order:
                    self.assertEqual(project.run("apply", label)[0], 0, label)
            self.assertEqual(project.context().config.engagement, "active")
            self.assertEqual(project.run("check")[0], 0)

    def test_list_keys_and_step_lists_are_set_too(self):
        with Project(init=True) as project:
            for key, value, shown in (("changes.ignore", ".git, node_modules, target", "[.git, node_modules, target]"),
                                      ("checkpoints.close.steps", "[bundle, marks, steers, mint, surface]", "[bundle, marks, steers, mint, surface]"),
                                      ("stores.decisions.label.prefix", "DEC", "DEC"), ("stores.decisions.label.digits", "4", "4")):
                code, out, err = config(project, "set", key, value)
                self.assertEqual(code, 0, (key, out, err))
                label = re.search(r"Drafted (P-\d+): `%s` would go from .* to `%s`" % (re.escape(key), re.escape(shown)), out).group(1)
                self.assertEqual(project.run("apply", label)[0], 0, key)
                self.assertEqual(project.run("check")[0], 0, key)
            self.assertEqual(project.context().config.stores["decisions"].prefix, "DEC")
            self.assertEqual(project.context().config.checkpoints["close"].steps, ["bundle", "marks", "steers", "mint", "surface"])

    def test_the_skill_names_only_what_the_engine_takes_and_keeps_its_rules(self):
        text = " ".join(support.read(os.path.join(support.REPO, "skills", "vesta-config", "SKILL.md")).split())
        used = set(re.findall(r"`vesta ([a-z]+)", text))
        self.assertEqual(used - set(manifest.COMMANDS), set())
        self.assertTrue({"config", "setting", "apply", "reject", "proposals", "version"} <= used)
        with Project(init=True) as project:
            for arguments in (("config",), ("setting", "jotting"), ("setting", "jotting", "here"), ("config", "set", "engagement", "quiet")):
                self.assertEqual(project.run(*arguments)[0], 0, arguments)
        for wanted in ("Never edit `vesta/vesta.yml`", "approved by its id in this conversation", "Never settle by guessing",
                       "engine 0.3.0 or later", "cannot tell whether the owner approved it", "is a decision, not configuration"):
            self.assertIn(wanted, text)
        readme = " ".join(support.read(os.path.join(support.REPO, "README.md")).split())
        self.assertIn("`/vesta-config`", readme)
        self.assertIn("six agent skills", readme)


class Skills(unittest.TestCase):
    def read(self, name):
        return " ".join(support.read(os.path.join(support.REPO, "skills", name, "SKILL.md")).split())

    def test_the_pointer_block_holds_no_answers_text_either(self):
        block = support.read(os.path.join(support.ENGINE, "templates", "pointer-block.md"))
        self.assertNotIn("jot", block)
        self.assertIn("who notes a correction differs by machine", " ".join(block.split()))

    def test_no_skill_holds_what_only_one_answer_of_a_setting_needs(self):
        for name in ("vesta-hook", "vesta-insight"):
            text = self.read(name)
            self.assertNotIn("jot --steer", text, name)
            self.assertIn("differs by machine", text)
        text = self.read("vesta-backfill")
        self.assertIn("`vesta history where`", text)
        for gone in ("you are running in Claude Code", "you are running in another harness", "ask for one more than n"):
            self.assertNotIn(gone, text)
        self.assertIn("carried out aside, run the command it names", self.read("vesta-insight"))

    def test_where_to_read_from_is_said_for_the_harness_in_effect_and_no_folder_is_listed(self):
        with Project(init=True) as project, Home(project) as home:
            code, out, err = project.run("history", "where")
            self.assertEqual(code, 0, err)
            self.assertIn("the engine cannot find the conversations of the harness this command was started from", out)
            self.assertNotIn("Claude Code", out)
            in_claude(project)
            out = project.run("history", "where")[1]
            self.assertIn("Ask the owner whether to look in the folder Claude Code keeps for this project: %s" % home.folder.replace("\\", "/"), out)
            self.assertLess(out.index("Ask the owner whether to look"), out.index("On a yes, run `history`"))
            self.assertNotIn("cannot find the conversations of the harness", out)
            self.assertFalse(os.path.exists(home.folder))  # nothing was looked at
            out = project.run("history", "where", "--in", "my notes")[1]
            self.assertIn("Run `history sources --in 'my notes'`", out)
            self.assertEqual(project.run("history", "where", "x")[0], 2)

    def test_the_readme_and_the_internals_tell_a_new_user_what_each_answer_does(self):
        readme = " ".join(support.read(os.path.join(support.REPO, "README.md")).split())
        internals = " ".join(support.read(os.path.join(support.ENGINE, "templates", "vesta", "INTERNALS.md")).split())
        for text in (readme, internals):
            for wanted in ("`jotting`", "`review`", "`harness`", "`here`", "`later`", "`aside`", "setting"):
                self.assertIn(wanted, text)
        self.assertIn("## Settings", support.read(os.path.join(support.ENGINE, "templates", "vesta", "INTERNALS.md")))
        self.assertIn("settings.local.json", readme)
        self.assertIn("fall back to `here`", readme)


if __name__ == "__main__":
    unittest.main()
