"""Cases an adversarial review of slice 2 found. Each failed before its fix."""
import io
import os
import subprocess
import sys
import unittest

import support
import fixtures
from fixtures import BODY, Project, decision
from kernel import yamlsubset
from kernel.errors import Refusal
from kernel.tree import DiskTree, Overlay

FENCE = "`" * 3


def config_with(change):
    config = yamlsubset.read(yamlsubset.write(fixtures.CONFIG))
    change(config)
    return config


class NothingEndsInATraceback(unittest.TestCase):
    def test_a_condition_with_a_bad_argument_is_a_finding_and_does_not_run(self):
        for argument in ("body-max:abc", "body-max:", "body-max:-5", "body-max:0", "no-labels:"):
            with Project() as project:
                project.add_notes_store()
                project.write("vesta/notes/SCHEMA.md", project.read("vesta/notes/SCHEMA.md").replace("retired-reason]", '"%s"]' % argument))
                project.put({"uid": "0000000a", "id": "N-01", "state": "accepted", "cue": "x", "stakes": "", "unless": "", "areas": [],
                             "watch": [], "gone-because": ""}, "# A note\n\n## Note\n- False if: never.\n", store="notes")
                code, out, err = project.run("check")
                self.assertEqual((code, err), (1, ""), argument)
                self.assertEqual(len(project.check()), 1, argument)

    def test_a_configuration_or_schema_that_is_not_utf8(self):
        with Project() as project:
            with open(project.path("vesta/vesta.yml"), "wb") as handle:
                handle.write(b"schema: 1\nowner: \xff\n")
            code, out, err = project.run("version")
            self.assertEqual(code, 2)
            self.assertIn("vesta/vesta.yml is not UTF-8 text", err)
        with Project() as project:
            with open(project.path("vesta/decisions/SCHEMA.md"), "wb") as handle:
                handle.write(b"\xff\xfe")
            code, out, err = project.run("check")
            self.assertEqual((code, err), (1, ""))
            self.assertIn("error layout vesta/decisions/SCHEMA.md:1 the file is not UTF-8 text", out)

    def test_a_store_path_or_label_the_configuration_may_not_hold(self):
        cases = [
            (lambda c: c["stores"]["decisions"].update(path=".."), "`stores.decisions.path` is `..`; it must name a folder under vesta/"),
            (lambda c: c["stores"]["decisions"].update(path="a/../../b"), "it must name a folder under vesta/"),
            (lambda c: c["stores"]["decisions"]["label"].update(prefix="DEC-A"), "it must be letters and digits, opening with a letter"),
            (lambda c: c["stores"]["decisions"]["label"].update(prefix="../x"), "it must be letters and digits"),
            (lambda c: c["stores"]["decisions"]["label"].update(digits=-1), "it must be a whole number, zero or more"),
            (lambda c: c["checks"]["run"].append("records"), "`checks.run` names `records` 2 times; name it once"),
            (lambda c: c["stores"].update(copy=dict(c["stores"]["decisions"])), "which is also the folder of the store `decisions`"),
        ]
        for change, phrase in cases:
            with Project(config_with(change)) as project:
                code, out, err = project.run("check")
                self.assertEqual((code, err), (1, ""), phrase)
                self.assertIn(phrase, out)

    def test_an_unexpected_error_is_a_plain_message_and_exit_2(self):
        from cli import main, manifest
        import types
        module = types.ModuleType("boom")
        module.run = lambda context, arguments: 1 / 0
        with Project() as project:
            original = manifest.command
            manifest.command = lambda name: module
            try:
                out, err = io.StringIO(), io.StringIO()
                code = main.main(["version"], root=project.root, out=out, err=err)
            finally:
                manifest.command = original
            self.assertEqual(code, 2)
            self.assertIn("stopped on an error it did not expect (ZeroDivisionError", err.getvalue())

    def test_output_survives_a_console_that_is_not_utf8(self):
        with Project() as project:
            project.put(decision(when="отправка отчёта клиенту — 報告書を送る"))
            engine = os.path.join(project.root, "vesta", ".engine")
            import shutil
            shutil.copytree(support.ENGINE, engine, ignore=shutil.ignore_patterns("tests", "__pycache__"))
            environment = dict(os.environ, PYTHONIOENCODING="cp1252")
            result = subprocess.run([sys.executable, engine, "index"], capture_output=True, env=environment)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("отправка отчёта".encode("utf-8"), result.stdout)


class CheckDoesNotPassWhatItDidNotRead(unittest.TestCase):
    def test_with_no_check_to_run_it_says_so_and_exits_2(self):
        for text in ("schema: 1\n", ""):
            with Project(text, stores=()) as project:
                code, out, _ = project.run("check")
                self.assertEqual(code, 2)
                self.assertIn("No check ran", out)
                self.assertNotIn("0 errors", out)

    def test_an_unknown_check_id_is_reported_even_where_config_is_not_run_and_a_check_runs_once(self):
        config = config_with(lambda c: c["checks"].update(run=["bogus", "records", "records"]))
        with Project(config) as project:
            project.put(decision(why=""))
            code, out, _ = project.run("check")
            self.assertEqual(code, 1)
            self.assertIn("names the check `bogus`, which this engine does not have; it did not run", out)
            self.assertEqual(out.count("the field `why` is empty"), 1)
            self.assertEqual(out.count("- `records`:"), 1)

    def test_records_reports_a_store_it_could_not_read(self):
        config = config_with(lambda c: c["checks"].update(run=["records", "lengths"]))
        with Project(config) as project:
            project.write("vesta/decisions/SCHEMA.md", "# broken\n")
            project.put(decision(why=""))
            code, out, _ = project.run("check")
            self.assertEqual(code, 1)
            self.assertIn("the records of the store `decisions` were not checked", out)

    def test_a_check_the_configuration_does_not_name_is_never_imported(self):
        code = (
            "import sys, io; sys.path.insert(0, %r); from cli import main; "
            "code = main.main(['check'], root=%r, out=io.StringIO(), err=io.StringIO()); "
            "print(code, 'checks.layout' in sys.modules, 'checks.records' in sys.modules, 'checks.lengths' in sys.modules)"
        )
        config = config_with(lambda c: c["checks"].update(run=["layout"]))
        with Project(config) as project:
            result = subprocess.run([sys.executable, "-c", code % (support.ENGINE, project.root)], capture_output=True, text=True)
            self.assertEqual(result.stdout.strip(), "0 True False False", result.stderr)


class NothingLeavesTheIndexSilently(unittest.TestCase):
    def test_a_record_that_does_not_read_is_named_by_index_and_by_show(self):
        with Project() as project:
            project.put(decision("D-001", "0000000a"))
            project.write("vesta/decisions/D-002.md", "---\nuid: 0000000b\nid: D-002\nstatus: *x\n---\n# T\n")
            code, out, _ = project.run("index")
            self.assertEqual(code, 0)
            self.assertIn("**Not everything is listed.**", out)
            self.assertIn("- vesta/decisions/D-002.md does not read", out)
            code, _, err = project.run("show", "D-002")
            self.assertEqual(code, 2)
            self.assertIn("vesta/decisions/D-002.md is there and does not read", err)

    def test_a_store_that_does_not_read_is_named(self):
        with Project() as project:
            project.put(decision())
            project.write("vesta/decisions/SCHEMA.md", "# broken\n")
            _, out, _ = project.run("index")
            self.assertIn("- the store `decisions` cannot be read, so none of its records is here", out)
            code, _, err = project.run("index", "--store", "decisions")
            self.assertEqual(code, 2)
            self.assertIn("the store `decisions` cannot be read", err)
            self.assertIn("cannot be read", project.run("show", "D-001")[2])

    def test_a_file_in_the_wrong_place_is_a_finding(self):
        with Project() as project:
            project.put(decision())
            project.write("vesta/decisions/archive/D-002.md", project.read("vesta/decisions/D-001.md"))
            found = project.check()
            self.assertEqual(len(found), 1, found)
            self.assertIn("error layout vesta/decisions/archive/D-002.md:1", found[0])
            self.assertIn("the engine does not read it", found[0])

    def test_a_record_without_a_status_prints_a_plain_pointer_under_all(self):
        with Project() as project:
            fields = decision()
            fields["status"] = ["a"]
            project.put(fields)
            _, out, _ = project.run("index", "--all")
            self.assertIn("D-001  not in force (status: none)", out)
            self.assertNotIn("['a']", out)

    def test_index_takes_only_a_store_that_has_an_index_and_refuses_stray_arguments(self):
        with Project(init=True) as project:
            code, _, err = project.run("index", "--store", "observations")
            self.assertEqual(code, 2)
            self.assertIn("is not a store that has an index; those are: decisions", err)
            for arguments in (["index", "extra"], ["check", "x"], ["version", "junk"], ["scopes", "/"], ["scopes", "./"], ["show", ""]):
                self.assertEqual(project.run(*arguments)[0], 2, arguments)

    def test_a_recalled_store_needs_a_when_role(self):
        with Project() as project:
            project.add_notes_store()
            project.write("vesta/notes/SCHEMA.md", project.read("vesta/notes/SCHEMA.md").replace("  when: cue\n", ""))
            self.assertIn("names no field for the index role `when`", "\n".join(project.check()))


class WriteGuard(unittest.TestCase):
    def test_a_record_is_written_only_at_its_own_place_in_its_store(self):
        with Project() as project:
            project.put(decision())
            store = project.store()
            for path in ("vesta/vesta.yml", "vesta/decisions/README.md", "vesta/decisions/D-002.md", "vesta/elsewhere/D-001.md"):
                record = store.get("D-001").copy()
                record.path = path
                with self.assertRaises(Refusal, msg=path):
                    store.write(record)
            self.assertTrue(project.read("vesta/vesta.yml").startswith("schema: 1"))

    def test_a_file_that_does_not_read_is_not_written_over(self):
        with Project() as project:
            project.put(decision("D-001", "0000000a"))
            project.write("vesta/decisions/D-002.md", "hand-written, no frontmatter\n")
            store = project.store()
            record = store.get("D-001").copy()
            record.fields.update(uid="0000000b", id="D-002")
            record.path = ""
            with self.assertRaises(Refusal):
                store.write(record)
            self.assertEqual(project.read("vesta/decisions/D-002.md"), "hand-written, no frontmatter\n")

    def test_a_key_the_schema_does_not_list_is_not_written(self):
        with Project() as project:
            project.put(decision())
            store = project.store()
            record = store.get("D-001")
            record.fields["owner"] = "someone"
            with self.assertRaises(Refusal):
                store.write(record)

    def test_a_store_over_an_overlay_reads_what_it_wrote_and_keeps_fields_frozen(self):
        from cli import build
        with Project() as project:
            project.put(decision("D-001", "0000000a"))
            context = project.context()
            overlay = Overlay(DiskTree(project.root))
            stores = build.stores_over(overlay, context.config, context.clock)
            store = stores.get("decisions")
            new = store.get("D-001").copy()
            new.fields.update(uid="0000000b", id="D-002")
            new.path = ""
            store.write(new)
            again = store.get("D-002")
            again.fields["when"] = "another moment"
            store.write(again)
            self.assertEqual(store.get("D-002").get("when"), "another moment")
            frozen = store.get("D-002")
            frozen.fields["decided"] = "2026-09-09"
            with self.assertRaises(Refusal):
                store.write(frozen)
            self.assertFalse(os.path.exists(project.path("vesta/decisions/D-002.md")))
            self.assertEqual(store.next_id("x")[1], "D-003")


class Lifecycle(unittest.TestCase):
    """The lifecycle roles default to the fields of their own names; a schema block may name others."""

    def note(self, **changes):
        fields = {"uid": "0000000a", "id": "N-01", "state": "accepted", "cue": "writing to the printer", "stakes": "", "unless": "",
                  "areas": ["print/"], "watch": [], "gone-because": ""}
        fields.update(changes)
        return fields

    def test_a_store_that_names_its_own_status_field_is_retired_by_it(self):
        body = "# A note\n\n## Note\n- False if: the printer changes its day.\n"
        with Project() as project:
            project.add_notes_store()
            project.put(self.note(), body, store="notes")
            self.assertIn("N-01  [print/]", project.run("index")[1])
            self.assertIn("`print/a.pdf`: N-01", project.run("scopes", "print/a.pdf")[1])
            project.put(self.note(state="retired", **{"gone-because": "the printer closed"}), body, store="notes")
            self.assertEqual(project.check(), [])
            self.assertNotIn("N-01", project.run("index")[1])
            self.assertIn("N-01  retired: the printer closed", project.run("index", "--all")[1])
            self.assertIn("`print/a.pdf`: none", project.run("scopes", "print/a.pdf")[1])
            project.put(self.note(state="retired"), body, store="notes")
            self.assertIn("a retired record says why in `gone-because`", project.check()[0])

    def test_the_shipped_stores_name_no_lifecycle_field_and_use_the_defaults(self):
        with Project(init=True) as project:
            context = project.context()
            self.assertEqual(context.stores.get("decisions").type.lifecycle, {})
            self.assertEqual(context.stores.get("decisions").type.life_field("status"), "status")
            self.assertEqual(context.stores.get("decisions").type.life_field("superseded-by"), "superseded-by")
            self.assertEqual(context.stores.get("observations").type.life_field("disposition"), "disposition")
            self.assertIsNone(context.stores.get("observations").type.life_field("status"))
            for name in ("decisions", "observations", "proposals"):
                self.assertNotIn("lifecycle:", project.read("vesta/%s/SCHEMA.md" % name))

    def test_a_lifecycle_key_that_does_not_read_is_a_finding(self):
        cases = [
            ("  status: state\n", "  standing: state\n", "`standing` is not a lifecycle role; the roles are status, supersedes, superseded-by, retired-because, disposition"),
            ("  status: state\n", "  status: mood\n", "the lifecycle role `status` names `mood`, which is not a field"),
            ("  retired-because: gone-because\n", "  retired-because: areas\n", "the lifecycle role `retired-because` names `areas`, whose type is `list`"),
        ]
        for old, new, phrase in cases:
            with Project() as project:
                project.add_notes_store()
                text = project.read("vesta/notes/SCHEMA.md")
                self.assertIn(old, text)
                project.write("vesta/notes/SCHEMA.md", text.replace(old, new))
                self.assertIn(phrase, "\n".join(project.check()))


class SchemaBlock(unittest.TestCase):
    def problems(self, old, new):
        with Project() as project:
            project.add_notes_store()
            text = project.read("vesta/notes/SCHEMA.md")
            self.assertIn(old, text)
            project.write("vesta/notes/SCHEMA.md", text.replace(old, new, 1))
            return "\n".join(project.check())

    def test_a_key_of_the_wrong_kind_is_a_finding_not_a_changed_rule(self):
        cases = [
            ("    required: true\n    mutable: true\n  - name: cue", "    required: yes\n    mutable: true\n  - name: cue", "`required` of the field `state` is `yes`; it must be `true` or `false`"),
            ("    values: [accepted, superseded, retired]", "    values: accepted", "`values` of the field `state` must be a list of text"),
            ("  - name: gone-because\n    type: text", "  - name: gone-because\n    type: text\n    required-when: state in ,", "must have the form `<field> in <value>, <value>`"),
            ("  - name: Note\n    required: true", "  - name: Note\n    required: true\n  - name: Note\n    required: false", "the section `Note` is listed twice"),
            ("  when: cue", "  when: areas", "the index role `when` names `areas`, whose type is `list`"),
            ("  paths: areas", "  paths: cue", "the index role `paths` names `cue`, whose type is `text`"),
            ("    type: triggers", "    type: wishes", "has the type `wishes`"),
            ("conditions: [falsifier-or-trigger, retired-reason]", "conditions: [true]", "`conditions` must be a list of condition names"),
        ]
        for old, new, phrase in cases:
            self.assertIn(phrase, self.problems(old, new), phrase)

    def test_an_enum_pattern_matches_the_whole_value(self):
        with Project() as project:
            project.add_notes_store()
            text = project.read("vesta/notes/SCHEMA.md").replace("    values: [accepted, superseded, retired]", "    values: [superseded, retired]\n    patterns:\n      - acc|zzz")
            project.write("vesta/notes/SCHEMA.md", text)
            project.put({"uid": "0000000a", "id": "N-01", "state": "accepted", "cue": "x", "stakes": "", "unless": "", "areas": [],
                         "watch": [], "gone-because": ""}, "# A note\n\n## Note\n- False if: never.\n", store="notes")
            found = project.check()
            self.assertEqual(len(found), 1, found)
            self.assertIn("the field `state` is `accepted`; it must be one of", found[0])


OBSERVATION = {
    "uid": "0000000a", "id": "O-20260105-0000000a", "date": "2026-01-05", "session": "S-20260105-1c0e", "via": "lens:friction",
    "anchor": "scripts/release.sh", "record": "", "recheck": "", "steer-kind": "", "moment": "", "missed-by": "",
    "disposition": "open", "held": [],
}
NOTICED = "# The release script asks for the version three times\n\nEach stage prompts for the version.\n"


class OpenArchiveLayout(unittest.TestCase):
    """The second layout, with the conditions and field kinds only that store uses."""

    def put(self, project, folder="open", body=NOTICED, **changes):
        fields = dict(OBSERVATION, **changes)
        path = "vesta/observations/%s/%s.md" % (folder, fields["id"])
        project.write(path, "---\n" + yamlsubset.write(fields) + "---\n" + body)
        return path

    def test_records_are_read_from_open_and_from_each_archive_folder(self):
        with Project(init=True) as project:
            self.put(project)
            self.put(project, "archive/pass-001", uid="0000000b", id="O-20260105-0000000b", disposition="read (pass-001)")
            self.put(project, "archive/direct", uid="0000000c", id="O-20260105-0000000c", disposition="dropped — noise")
            self.assertEqual(project.check(), [])
            store = project.store("observations")
            self.assertEqual(len(store.list()), 3)
            self.assertEqual(store.locate("0000000b"), "vesta/observations/archive/pass-001/O-20260105-0000000b.md")
            uid, label = store.next_id("a title")
            self.assertEqual(label, "O-20260105-" + uid)

    def test_each_condition_and_field_kind_of_that_store(self):
        cases = [
            (dict(disposition="read (pass-001)"), None, "open", "is under `open/` and its `disposition` is not `open`"),
            ({}, None, "archive/pass-001", "is under `archive/` and its `disposition` is `open`"),
            ({}, NOTICED + "x" * 600, "open", "characters; the most is 600"),
            ({}, NOTICED + "Fix: pass the version along.\n", "open", "a line of the body opens `Fix:`"),
            (dict(via="lens:Friction!"), None, "open", "the field `via` is `lens:Friction!`; it must be one of"),
            (dict(via="owner-steer"), None, "open", "the field `steer-kind` is empty; it is required when `via` is `owner-steer`"),
            (dict(record="D-001@0000000f"), None, "open", "the field `record` is filled; it is filled only when"),
            (dict(date="5 January"), None, "open", "must be a date written YYYY-MM-DD"),
            (dict(id="O-1"), None, "open", "is not in the form this store's records take, as `O-<date>-<internal id>`"),
        ]
        for changes, body, folder, phrase in cases:
            with Project(init=True) as project:
                path = self.put(project, folder, body or NOTICED, **changes)
                found = [line for line in project.check() if line.startswith("error records ")]
                if changes.get("via") == "owner-steer":
                    self.assertEqual(len(found), 3, found)
                else:
                    self.assertEqual(len(found), 1, "%s: %s" % (phrase, found))
                self.assertIn(phrase, "\n".join(found))

    def test_an_integer_field_and_a_store_with_no_title(self):
        schema = "\n".join([
            FENCE + "vesta-schema", "layout: flat", "title: none", "fields:", "  - name: uid", "    type: text", "    required: true",
            "  - name: id", "    type: text", "    required: true", "  - name: count", "    type: integer", "    required: true",
            "sections: []", FENCE, ""])
        config = config_with(lambda c: c["stores"].update(tallies={"path": "tallies", "kind": "register", "recall": "none", "governed": False,
                                                                  "label": {"prefix": "T", "digits": 2}}))
        with Project(config) as project:
            project.write("vesta/tallies/README.md", "# Tallies\n")
            project.write("vesta/tallies/SCHEMA.md", schema)
            project.write("vesta/tallies/T-01.md", "---\nuid: 0000000a\nid: T-01\ncount: 3\n---\nJust text.\n")
            self.assertEqual(project.check(), [])
            project.write("vesta/tallies/T-01.md", "---\nuid: 0000000a\nid: T-01\ncount: three\n---\n# A title\n")
            text = "\n".join(project.check())
            self.assertIn("the field `count` holds text; it must be a whole number", text)
            self.assertIn("a record of this store has no title line", text)


class Messages(unittest.TestCase):
    def test_help_lists_each_command_with_a_line(self):
        with Project() as project:
            for arguments in (["help"], ["--help"], ["index", "--help"]):
                code, out, _ = project.run(*arguments)
                self.assertEqual(code, 0)
                for name in ("version", "check", "show", "index", "scopes", "init", "doctor"):
                    self.assertRegex(out, r"\n  %s +\S" % name)

    def test_the_refusal_of_a_frozen_field_says_what_to_do_and_points_at_a_section_that_exists(self):
        with Project() as project:
            project.put(decision())
            store = project.store()
            record = store.get("D-001")
            record.fields["decided"] = "2026-02-02"
            with self.assertRaises(Refusal) as caught:
                store.write(record)
            self.assertIn("`supersede` proposal", caught.exception.message)
            self.assertEqual(caught.exception.rule, "vesta/decisions/SCHEMA.md, Fields")
            schema = project.read("vesta/decisions/SCHEMA.md")
            self.assertIn("\n## Fields\n", schema)
            self.assertIn("fixed once", schema)


if __name__ == "__main__":
    unittest.main()
