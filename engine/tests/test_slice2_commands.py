import os
import unittest

import support
import fixtures
from fixtures import BODY, Project, decision
from kernel import yamlsubset
from kernel.version import ENGINE
from matchers import scope

GOLDEN = os.path.join(support.TESTS, "golden")
SENTINEL = "ZZSENTINELZZ"

LONG_WHEN = (
    "adding or changing a call to an outside service; choosing a timeout or a retry count; a request that "
    "hangs or fails now and then; a job that never finishes; a queue that stops draining for no stated reason"
)


def five(project):
    """Five decisions that between them use every part of an index block."""
    body = BODY.replace("# Every figure", "# " + SENTINEL + " every figure").replace("Reports are", SENTINEL + " reports are")
    body = body.replace("Every figure is checked against", SENTINEL + " every figure is checked against").replace("- False if: the source", "- False if: " + SENTINEL + " the source")
    assert body.count(SENTINEL) == 4
    project.put(decision("D-001", "0000000a", scopes=["reports/", "letters/"], **{"except": "internal working notes"}), body)
    project.put(decision("D-002", "0000000b", when=LONG_WHEN, why="an unbounded wait in one call stalls the whole job queue",
                         scopes=["src/integrations/", "src/http/"],
                         triggers=[
                             {"id": "t1", "if": "an outside service documents a slower response", "then": "re-decide the timeout", "probe": "", "resolved": ""},
                             {"id": "t2", "if": "the queue is replaced", "then": "retire this", "probe": "", "resolved": "D-005"},
                         ]), body)
    project.put(decision("D-003", "0000000c", status="superseded", superseded_by="D-004@0000000d"), body)
    project.put(decision("D-004", "0000000d", when="naming a client in a letter", why="a misspelled name reads as carelessness",
                         supersedes=["D-003@0000000c"]), body)
    project.put(decision("D-005", "0000000e", status="retired", retired_because="the fax line was closed on 2026-01-02"), body)


class Index(unittest.TestCase):
    def golden(self, name, text):
        path = os.path.join(GOLDEN, name)
        self.assertTrue(os.path.isfile(path), "the golden file %s is missing" % name)
        self.assertEqual(text, support.read(path))

    def test_the_index_of_five_decisions_equals_the_golden_file(self):
        with Project() as project:
            five(project)
            self.assertEqual(project.check(), [])
            code, out, _ = project.run("index")
            self.assertEqual(code, 0)
            self.golden("index-five.md", out)
            code, everything, _ = project.run("index", "--all")
            self.golden("index-five-all.md", everything)

    def test_the_index_holds_no_title_and_no_body_text(self):
        with Project() as project:
            five(project)
            for arguments in (["index"], ["index", "--all"], ["index", "--store", "decisions"], ["scopes", "reports/a.md"]):
                _, out, _ = project.run(*arguments)
                self.assertNotIn(SENTINEL, out, arguments)
            self.assertIn(SENTINEL, project.run("show", "D-001")[1])

    def test_a_block_is_five_lines_at_most_whatever_the_length_of_its_lines(self):
        with Project() as project:
            project.put(decision(when="w " * 150, why="y " * 100, **{"except": "e " * 100}))
            _, out, _ = project.run("index")
            block = out.split("```")[1].strip("\n").split("\n")
            self.assertEqual(len(block), 5, block)

    def test_an_empty_store_prints_none(self):
        with Project() as project:
            _, out, _ = project.run("index")
            self.assertIn("## decisions\n\nnone\n", out)

    def test_an_unknown_store_is_a_usage_error(self):
        with Project() as project:
            code, _, err = project.run("index", "--store", "nope")
            self.assertEqual(code, 2)
            self.assertIn("`nope` is not a store", err)


class Scope(unittest.TestCase):
    def test_prefix_by_segment(self):
        self.assertTrue(scope.covers("src/http", "src/http/client.py"))
        self.assertTrue(scope.covers("src/http/", "src/http/client.py"))
        self.assertTrue(scope.covers("src/http/", "src/http"))
        self.assertFalse(scope.covers("src/http", "src/httpx/a.py"))
        self.assertFalse(scope.covers("src/http/", "src/a.py"))
        self.assertFalse(scope.covers("", "src/a.py"))

    def test_a_trailing_slash_query_reaches_scopes_inside_it(self):
        self.assertTrue(scope.reaches("src/http/", "src/"))
        self.assertFalse(scope.reaches("src/http/", "src"))
        self.assertFalse(scope.reaches("src/http/", "docs/"))
        self.assertTrue(scope.reaches("src/", "src/http/"))

    def test_the_scopes_command(self):
        with Project() as project:
            five(project)
            code, out, _ = project.run("scopes", "reports/2026/q1.md", "src/", "src/httpx/a.py", "letters")
            self.assertEqual(code, 0)
            self.assertIn("- `reports/2026/q1.md`: D-001\n", out)
            self.assertIn("- `src/`: D-002\n", out)
            self.assertIn("- `src/httpx/a.py`: none\n", out)
            self.assertIn("- `letters`: D-001\n", out)
            self.assertEqual(project.run("scopes")[0], 2)

    def test_a_record_not_in_force_is_not_matched(self):
        with Project() as project:
            project.put(decision("D-001", "0000000a", status="retired", retired_because="gone", scopes=["reports/"]))
            self.assertIn("`reports/a.md`: none", project.run("scopes", "reports/a.md")[1])


class FixtureStore(unittest.TestCase):
    """A store added by configuration and a SCHEMA.md alone, with other field names in its index roles."""

    def note(self, label, uid, **changes):
        fields = {"uid": uid, "id": label, "state": "accepted", "cue": "writing to the printer", "stakes": "a late proof costs a week",
                  "unless": "", "areas": ["print/"], "watch": [], "gone-because": ""}
        fields.update(changes)
        return fields

    def test_it_loads_lists_checks_and_prints_an_index_with_no_engine_change(self):
        with Project() as project:
            project.add_notes_store()
            body = "# Proofs go to the printer by Tuesday\n\n## Note\nProofs go by Tuesday.\n- False if: the printer changes its day.\n"
            project.put(self.note("N-01", "0000000a"), body, store="notes")
            project.put(self.note("N-02", "0000000b", areas=[], unless="reprints", watch=[
                {"id": "t1", "if": "the printer changes", "then": "check the day", "probe": "", "resolved": ""}]),
                body.replace("- False if: the printer changes its day.\n", ""), store="notes")
            project.put(decision("D-001", "0000000c", scopes=["print/"]))
            self.assertEqual(project.check(), [])
            store = project.store("notes")
            self.assertEqual([record.label for record in store.list()], ["N-01", "N-02"])
            self.assertEqual(store.next_id("x")[1], "N-03")
            _, out, _ = project.run("index")
            self.assertIn("## notes\n\n```\nN-01  [print/]\n  when:   writing to the printer\n  why:    a late proof costs a week\n\nN-02\n", out)
            self.assertIn("  except: reprints\n", out)
            self.assertIn("  unstable-if (t1): the printer changes\n", out)
            self.assertIn("- `print/proof.pdf`: D-001, N-01\n", project.run("scopes", "print/proof.pdf")[1])
            self.assertIn("Proofs go by Tuesday.", project.run("show", "N-01")[1])
            project.put(self.note("N-03", "0000000d", cue=""), body, store="notes")
            found = project.check()
            self.assertEqual(len(found), 1)
            self.assertIn("the field `cue` is empty", found[0])
            project.put(self.note("N-03", "0000000d", cue="c " * 160), body, store="notes")
            self.assertIn("warning lengths vesta/notes/N-03.md:", project.check()[0])

    def test_no_shared_module_names_a_field_of_a_store(self):
        # `decided` and `approved-by` are lifecycle roles, named once in the model; a store's schema
        # may give either role to a field of another name.
        names = ['"scopes"', '"related"', '"cue"', '"stakes"']
        roles = ['"approved-by"', '"decided"']
        for package in ("kernel", "model", "stores", "matchers", "session", "steps", "proposals", "checks"):
            for folder, _, leaves in os.walk(os.path.join(support.ENGINE, package)):
                for leaf in leaves:
                    if not leaf.endswith(".py"):
                        continue
                    text = support.read(os.path.join(folder, leaf))
                    for name in names + ([] if (package, leaf) == ("model", "abstractions.py") else roles):
                        self.assertFalse(name in text, "%s/%s names the field %s" % (package, leaf, name))


class Config(unittest.TestCase):
    def findings(self, change):
        config = yamlsubset.read(yamlsubset.write(fixtures.CONFIG))
        change(config)
        with Project(config) as project:
            return project.check()

    def test_the_fixture_configuration_has_no_finding(self):
        self.assertEqual(self.findings(lambda config: None), [])

    def test_an_unknown_key_is_a_finding_with_its_line(self):
        def change(config):
            config["colour"] = "blue"
            config["stores"]["decisions"]["label"]["suffix"] = "x"
        found = self.findings(change)
        self.assertEqual(len(found), 2, found)
        self.assertTrue(all(line.startswith("error config vesta/vesta.yml:") for line in found))
        text = "\n".join(found)
        self.assertIn("the key `colour` is not a key of the configuration", text)
        self.assertIn("the key `stores.decisions.label.suffix` is not a key", text)
        self.assertNotIn("vesta.yml:1 ", text)

    def test_an_id_absent_from_the_manifest_is_a_finding(self):
        def change(config):
            config["checks"]["run"].append("spelling")
            config["proposals"] = {"kinds": ["transmute"]}
            config["checkpoints"] = {"start": {"walk": "walks/start.md", "steps": ["divine"]}}
            config["adapters"] = {"changes": "telepathy", "capture": ["osmosis"]}
        found = self.findings(change)
        text = "\n".join(found)
        self.assertEqual(len(found), 5, found)
        for phrase in ("the check `spelling`", "the proposal kind `transmute`", "the step `divine`",
                       "the change source `telepathy`", "the capture source `osmosis`"):
            self.assertIn(phrase + ", which this engine does not have", text)

    def test_a_value_of_the_wrong_kind_is_a_finding(self):
        def change(config):
            config["engagement"] = "loud"
            config["stores"]["decisions"]["governed"] = "yes"
        found = self.findings(change)
        self.assertEqual(len(found), 2, found)
        self.assertIn("`engagement` is `loud`; it must be one of quiet, standard, active", found[0])
        self.assertIn("`stores.decisions.governed` is `yes`; it must be true or false", found[1])

    def test_a_configuration_that_does_not_read_or_is_too_new_stops_every_command(self):
        with Project("schema: 1\nstores: {a: b}\n", stores=()) as project:
            code, _, err = project.run("check")
            self.assertEqual(code, 2)
            self.assertIn("vesta/vesta.yml:2", err)
        with Project("schema: 2\n", stores=()) as project:
            code, _, err = project.run("version")
            self.assertEqual(code, 2)
            self.assertIn("upgrade", err)

    def test_keys_left_out_take_their_first_values(self):
        with Project("schema: 1\n", stores=()) as project:
            config = project.context().config
            self.assertEqual((config.engagement, config.long_index_at, config.remind_open_observations, config.changes),
                             ("standard", 60, 25, "auto"))
            self.assertTrue(config.remind_learn and config.remind_pending)
            self.assertEqual((config.stores, config.checks, config.kinds), ({}, [], []))


class Layout(unittest.TestCase):
    def test_a_store_without_its_two_files_and_a_stored_index_are_findings(self):
        with Project() as project:
            os.remove(project.path("vesta/decisions/README.md"))
            project.write("vesta/decisions/INDEX.md", "# Index\n")
            found = project.check()
            self.assertEqual(len(found), 2, found)
            self.assertIn("error layout vesta/decisions/INDEX.md:1 an index is stored here", "\n".join(found))
            self.assertIn("has no README.md", "\n".join(found))

    def test_a_schema_file_with_no_block_two_blocks_or_a_bad_block(self):
        fence = "`" * 3
        block = fence + "vesta-schema\nlayout: flat\n" + fence + "\n"
        cases = [
            ("# Nothing\n", "holds 0 `vesta-schema` blocks"),
            (block + block, "holds 2 `vesta-schema` blocks"),
            (block, "`title` is nothing; it must be `required` or `none`"),
            (fence + "vesta-schema\nlayout: flat\n", "is never closed"),
            (fence + "vesta-schema\nlayout: *x\n" + fence + "\n", "a value may not open with `*`"),
        ]
        for text, phrase in cases:
            with Project() as project:
                project.write("vesta/decisions/SCHEMA.md", text)
                project.put(decision())
                found = project.check()
                self.assertTrue(found and all(" vesta/decisions/SCHEMA.md:" in line for line in found), found)
                self.assertIn("error records vesta/decisions/SCHEMA.md", found[-1])
                self.assertIn(phrase, "\n".join(found))

    def test_a_missing_store_folder(self):
        with Project(stores=()) as project:
            self.assertIn("the folder of the store `decisions` is missing", project.check()[0])


class Commands(unittest.TestCase):
    def test_version(self):
        with Project() as project:
            self.assertEqual(project.run("version"), (0, "engine %s\nschema 1\n" % ENGINE, ""))

    def test_show_prints_records_in_full_and_writes_nothing(self):
        with Project() as project:
            five(project)
            before = sorted(os.listdir(project.path("vesta")))
            code, out, _ = project.run("show", "D-001", "0000000d")
            self.assertEqual(code, 0)
            self.assertIn(project.read("vesta/decisions/D-001.md").rstrip("\n"), out)
            self.assertIn("id: D-004", out)
            self.assertEqual(sorted(os.listdir(project.path("vesta"))), before)
            code, _, err = project.run("show", "D-404")
            self.assertEqual(code, 2)
            self.assertIn("`D-404` names no record", err)

    def test_check_prints_what_each_check_does_not_verify_and_exits_1_on_an_error(self):
        with Project() as project:
            project.put(decision())
            code, out, _ = project.run("check")
            self.assertEqual(code, 0)
            for name in fixtures.CONFIG["checks"]["run"]:
                self.assertIn("- `%s`: " % name, out)
            self.assertIn("0 errors, 0 warnings.", out)
            project.put(decision(why=""))
            code, out, _ = project.run("check")
            self.assertEqual(code, 1)
            self.assertIn("1 error, 0 warnings.", out)

    def test_a_check_the_configuration_does_not_name_does_not_run(self):
        config = dict(fixtures.CONFIG, checks={"run": ["layout"]})
        with Project(config) as project:
            project.put(decision(why=""))
            code, out, _ = project.run("check")
            self.assertEqual(code, 0)
            self.assertNotIn("`records`", out)

    def test_an_unknown_command_and_no_command_are_usage_errors(self):
        with Project() as project:
            code, _, err = project.run("frobnicate")
            self.assertEqual(code, 2)
            self.assertIn("`frobnicate` is not a command", err)
            self.assertEqual(project.run()[0], 2)

    def test_without_a_configuration_the_command_says_to_set_up_first(self):
        with Project() as project:
            os.remove(project.path("vesta/vesta.yml"))
            code, _, err = project.run("check")
            self.assertEqual(code, 2)
            self.assertIn("/vesta-init", err)

    def test_a_commit_left_unfinished_is_put_back_and_reported_before_the_command_runs(self):
        from kernel import tree
        with Project() as project:
            project.put(decision())
            before = project.read("vesta/decisions/D-001.md")
            disk = tree.DiskTree(project.root)
            disk.write(tree.JOURNAL, '{"paths": {"vesta/decisions/D-001.md": %s, "vesta/decisions/D-002.md": null}}' % __import__("json").dumps(before))
            project.write("vesta/decisions/D-001.md", "half written")
            project.write("vesta/decisions/D-002.md", "half written")
            code, out, _ = project.run("check")
            self.assertEqual(code, 0, out)
            self.assertTrue(out.startswith("An earlier command stopped before it finished."))
            self.assertIn("- vesta/decisions/D-001.md\n- vesta/decisions/D-002.md\n", out)
            self.assertFalse(os.path.exists(project.path("vesta/decisions/D-002.md")))


if __name__ == "__main__":
    unittest.main()
