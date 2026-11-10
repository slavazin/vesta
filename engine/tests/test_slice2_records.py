import os
import unittest

import support
import fixtures
from fixtures import BODY, Project, decision
from kernel.errors import Refusal

VERBATIM = os.path.join(support.DATA, "verbatim")


def errors(lines):
    return [line for line in lines if line.startswith("error ")]


class Examples(unittest.TestCase):
    def test_both_decision_examples_pass_check(self):
        with Project() as project:
            project.write("vesta/decisions/D-004.md", support.read(os.path.join(VERBATIM, "decision-example-1.md")))
            project.write("vesta/decisions/D-002.md", support.read(os.path.join(VERBATIM, "decision-example-2.md")))
            code, out, _ = project.run("check")
            self.assertEqual(code, 0, out)
            self.assertIn("0 errors", out)
            for line in project.check():
                self.assertIn("not in the written form", line)

    def test_the_shipped_schema_carries_both_examples(self):
        text = support.read(os.path.join(fixtures.TEMPLATES, "decisions", "SCHEMA.md"))
        for name in ("decision-example-1.md", "decision-example-2.md"):
            self.assertIn(support.read(os.path.join(VERBATIM, name)), text)

    def test_a_valid_canonical_decision_has_no_finding(self):
        with Project() as project:
            project.put(decision())
            self.assertEqual(project.check(), [])


TRIGGER = {"id": "t1", "if": "the source sheet moves", "then": "re-derive the check", "probe": "", "resolved": ""}

# (name, changed fields, changed body or None, a phrase of the one finding)
FIELD_RULES = [
    ("uid empty", {"uid": ""}, None, "the field `uid` is empty"),
    ("uid malformed", {"uid": "xyz"}, None, "eight hexadecimal characters"),
    ("id empty", {"id": ""}, None, "the field `id` is empty"),
    ("status unknown", {"status": "proposed"}, None, "it must be one of `accepted`, `superseded`, `retired`"),
    ("status empty", {"status": ""}, None, "the field `status` is empty"),
    ("decided empty", {"decided": ""}, None, "the field `decided` is empty"),
    ("decided not a date", {"decided": "14 March"}, None, "a date written YYYY-MM-DD"),
    ("decided an impossible date", {"decided": "2026-02-30"}, None, "a date written YYYY-MM-DD"),
    ("approved-by empty", {"approved_by": ""}, None, "the field `approved-by` is empty"),
    ("when empty", {"when": ""}, None, "the field `when` is empty"),
    ("why empty", {"why": ""}, None, "the field `why` is empty"),
    ("when a number", {"when": 12}, None, "the field `when` holds a number; it must be one line of text; put it in double quotes"),
    ("scopes not a list", {"scopes": 3}, None, "the field `scopes` holds a number; it must be a list of text"),
    ("triggers not a list of mappings", {"triggers": ["t1"]}, None, "a list of triggers"),
    ("trigger id malformed", {"triggers": [dict(TRIGGER, id="one")]}, None, "trigger ids are `t1`, `t2`"),
    ("trigger id twice", {"triggers": [TRIGGER, TRIGGER]}, None, "occurs twice"),
    ("trigger without if", {"triggers": [dict(TRIGGER, **{"if": ""})]}, None, "has no `if`"),
    ("trigger then not an act", {"triggers": [dict(TRIGGER, then="think about it")]}, None, "opens with one of"),
    ("trigger with an unknown key", {"triggers": [dict(TRIGGER, note="x")]}, None, "has the key `note`"),
    ("superseded without a successor", {"status": "superseded"}, None, "the field `superseded-by` is empty; it is required when `status` is `superseded`"),
    ("a successor on an accepted record", {"superseded_by": "D-009@00000009"}, None, "the field `superseded-by` is filled"),
    ("retired without a reason", {"status": "retired"}, None, "the field `retired-because` is empty; it is required when `status` is `retired`"),
    ("a retirement reason on an accepted record", {"retired_because": "gone"}, None, "the field `retired-because` is filled"),
    ("an unknown key", {"owner": "someone"}, None, "the key `owner` is not a field of this store"),
    ("when a list", {"when": ["x", "y"]}, None, "the field `when` holds a list; it must be one line of text"),
    ("when only spaces", {"when": "   "}, None, "the field `when` is empty"),
    ("an empty scope", {"scopes": ["reports/", " "]}, None, "the field `scopes` has an empty item"),
    ("a reference that is a bare label", {"related": ["D-404"]}, None, "a record is named `<label>@<internal id>`"),
    ("a successor that is not a reference", {"status": "superseded", "superseded_by": "the new one"}, None, "a record is named `<label>@<internal id>`"),
    ("related not a list", {"related": "D-002@0000000b"}, None, "the field `related` holds text; it must be a list of text"),
    ("a second title", {}, BODY + "\n# Another title\n", "a second `# ` title line"),
    ("a section twice", {}, BODY.replace("## Warrant", "## Decision\nAgain.\n\n## Warrant"), "the section `## Decision` occurs twice"),
    ("no title", {}, BODY.split("\n", 1)[1], "opens with one `# ` title line"),
    ("no Context", {}, BODY.replace("## Context\nReports are drafted over several days.\n\n", ""), "the section `## Context` is missing"),
    ("no Decision", {}, BODY.replace("## Decision\nEvery figure is checked against the source on the day of sending.\n\n", ""), "the section `## Decision` is missing"),
    ("no Warrant", {"triggers": [TRIGGER]}, BODY.split("## Warrant")[0], "the section `## Warrant` is missing"),
    ("a section out of order", {}, BODY.replace("## Context", "## Consequences"). replace("## Decision", "## Context").replace("## Consequences", "## Decision", 1), "out of order"),
    ("an unknown section", {}, BODY + "\n## History\nIt was different before.\n", "the section `## History` is not a section of this store"),
]


class FieldRules(unittest.TestCase):
    def test_one_fixture_per_field_rule_fails_with_that_finding_and_no_other(self):
        for name, changes, body, phrase in FIELD_RULES:
            with Project() as project:
                fields = decision(**changes)
                project.put(fields, body if body is not None else BODY, name="D-001")
                found = project.check()
                self.assertEqual(len(found), 1, "%s: %s" % (name, found))
                self.assertTrue(found[0].startswith("error records vesta/decisions/D-001.md:"), found[0])
                self.assertIn(phrase, found[0], name)

    def test_a_missing_required_key_is_named_as_missing(self):
        with Project() as project:
            fields = decision()
            del fields["why"]
            project.put(fields)
            found = project.check()
            self.assertEqual(len(found), 1, found)
            self.assertIn("the field `why` is missing from the frontmatter", found[0])

    def test_a_label_takes_the_form_the_store_is_configured_with(self):
        with Project() as project:
            project.put(decision(label="banana"))
            found = project.check()
            self.assertEqual(len(found), 1, found)
            self.assertIn("the label `banana` is not in the form this store's records take, as `D-001`", found[0])
            os.remove(project.path("vesta/decisions/banana.md"))
            project.put(decision(label="D-01"))
            self.assertEqual(len(project.check()), 1)

    def test_the_label_equals_the_file_name(self):
        with Project() as project:
            project.put(decision(label="D-007"), name="D-001")
            found = project.check()
            self.assertEqual(len(found), 1, found)
            self.assertIn("the file is named `D-001.md`", found[0])

    def test_a_finding_names_the_line_of_its_field(self):
        with Project() as project:
            project.put(decision(why=""))
            line = project.check()[0]
            number = int(line.split(":")[1].split(" ")[0])
            self.assertEqual(project.read("vesta/decisions/D-001.md").split("\n")[number - 1], 'why: ""')

    def test_a_file_that_does_not_read_is_one_finding_with_its_line(self):
        with Project() as project:
            project.write("vesta/decisions/D-001.md", "---\nuid: 00000001\nid: D-001\nstatus: *x\n---\n# T\n")
            found = project.check()
            self.assertEqual(len(found), 1, found)
            self.assertIn("vesta/decisions/D-001.md:4 ", found[0])
            project.write("vesta/decisions/D-001.md", "# No frontmatter\n")
            self.assertEqual(len(project.check()), 1)


class Conditions(unittest.TestCase):
    def test_falsifier_or_trigger(self):
        body = BODY.replace("- False if: the source is frozen before drafting starts.", "- The source moved on 2026-01-02.")
        with Project() as project:
            project.put(decision(), body)
            found = project.check()
            self.assertEqual(len(found), 1, found)
            self.assertIn("states what would make it wrong", found[0])
            project.put(decision(triggers=[TRIGGER]), body)
            self.assertEqual(project.check(), [])
            project.put(decision(), body.replace("- The source moved", "- False if:\n- The source moved"))
            self.assertEqual(len(project.check()), 1, "an empty falsifier line does not count")
            project.put(decision(status="retired", retired_because="the reports stopped"), body)
            self.assertEqual(project.check(), [], "only an accepted record needs one")

    def test_successor_pair(self):
        with Project() as project:
            project.put(decision("D-001", "00000001", status="superseded", superseded_by="D-002@00000002"))
            found = project.check()
            self.assertEqual(len(found), 1, found)
            self.assertIn("which is not a record", found[0])
            project.put(decision("D-002", "00000002"))
            found = project.check()
            self.assertEqual(len(found), 1, found)
            self.assertIn("D-002 does not name this record as one it replaces (in its `supersedes`)", found[0])
            project.put(decision("D-002", "00000002", supersedes=["D-001@00000001"]))
            self.assertEqual(project.check(), [])

    def test_retired_reason_in_a_store_whose_schema_has_no_field_rule_for_it(self):
        with Project() as project:
            project.add_notes_store()
            fields = {"uid": "0000000a", "id": "N-01", "state": "retired", "cue": "x", "stakes": "", "unless": "",
                      "areas": [], "watch": [], "gone-because": ""}
            project.put(fields, "# A note\n\n## Note\nText.\n", store="notes")
            found = project.check()
            self.assertEqual(len(found), 1, found)
            self.assertIn("a retired record says why", found[0])

    def test_an_unregistered_condition_is_a_finding(self):
        with Project() as project:
            project.add_notes_store()
            schema = project.read("vesta/notes/SCHEMA.md").replace("retired-reason]", "never-heard-of]")
            project.write("vesta/notes/SCHEMA.md", schema)
            found = project.check()
            self.assertEqual(len(found), 1, found)
            self.assertIn("`never-heard-of` is not one this engine has", found[0])


class Ledger(unittest.TestCase):
    def test_a_ledger_refuses_a_write_that_changes_a_field_not_marked_mutable(self):
        with Project() as project:
            project.put(decision())
            store = project.store()
            record = store.get("D-001")
            for name, value in (("decided", "2026-02-02"), ("approved-by", "Someone Else"), ("uid", "0000000f"), ("id", "D-009"), ("supersedes", ["D-000@00000000"])):
                changed = record.copy()
                changed.fields[name] = value
                with self.assertRaises(Refusal, msg=name) as caught:
                    store.write(changed)
                if name != "uid":
                    self.assertIn("`%s`" % name, caught.exception.message)
                    self.assertIn("vesta/decisions/SCHEMA.md", caught.exception.rule)
                else:
                    self.assertIn("never written over", caught.exception.message)
            self.assertEqual(project.check(), [])

    def test_a_mutable_field_and_the_body_may_change(self):
        with Project() as project:
            project.put(decision())
            store = project.store()
            record = store.get("D-001")
            record.fields["when"] = "sending anything to a client; quoting a figure"
            record.fields["scopes"] = ["reports/"]
            store.write(record)
            self.assertEqual(project.store().get("D-001").get("scopes"), ["reports/"])
            self.assertEqual(project.check(), [])

    def test_a_register_store_takes_any_change(self):
        config = dict(fixtures.CONFIG)
        config["stores"] = {"decisions": dict(fixtures.CONFIG["stores"]["decisions"], kind="register")}
        with Project(config) as project:
            project.put(decision())
            store = project.store()
            record = store.get("D-001")
            record.fields["decided"] = "2026-02-02"
            store.write(record)
            self.assertEqual(project.store().get("D-001").get("decided"), "2026-02-02")

    def test_a_write_is_canonical_and_fills_every_field(self):
        with Project() as project:
            project.write("vesta/decisions/D-001.md", "\n".join([
                "---", "id: D-001", "uid: 0000000a", 'status: "accepted"', "decided: 2026-01-05", "approved-by: A. Reviewer",
                "when: sending anything to a client", "why: a stale figure goes out", "---", BODY]))
            self.assertEqual(len(project.check()), 1)
            self.assertIn("warning records", project.check()[0])
            store = project.store()
            store.write(store.get("D-001"))
            self.assertEqual(project.check(), [])
            text = project.read("vesta/decisions/D-001.md")
            self.assertTrue(text.startswith("---\nuid: 0000000a\nid: D-001\nstatus: accepted\n"))
            self.assertIn("\nscopes: []\ntriggers: []\nsupersedes: []\nsuperseded-by: \"\"\n", text)


class Identity(unittest.TestCase):
    def test_every_record_written_gets_a_unique_internal_id_and_the_next_label(self):
        with Project() as project:
            seen = set()
            for number in range(1, 31):
                store = project.store()
                uid, label = store.next_id("the same title")
                self.assertEqual(label, "D-%03d" % number)
                self.assertNotIn(uid, seen)
                seen.add(uid)
                project.put(decision(label, uid))
            self.assertEqual(project.check(), [])
            store = project.store()
            self.assertEqual(store.get("D-007").ref, "D-007@" + store.get("D-007").uid)

    def test_a_record_is_named_by_label_internal_id_or_both(self):
        with Project() as project:
            project.put(decision("D-001", "0000000a"))
            project.put(decision("D-002", "0000000b"))
            store = project.store()
            for name in ("D-002", "0000000b", "D-002@0000000b", "D-999@0000000b"):
                self.assertEqual(store.get(name).label, "D-002", name)
            self.assertIsNone(store.get("D-003"))
            self.assertIsNone(store.get("0000000c"))
            self.assertEqual(store.locate("D-001"), "vesta/decisions/D-001.md")

    def test_a_stale_label_half_still_resolves_and_check_warns(self):
        with Project() as project:
            project.put(decision("D-001", "0000000a", related=["D-077@0000000b"]))
            project.put(decision("D-002", "0000000b"))
            context = project.context()
            self.assertEqual(context.stores.resolve("D-077@0000000b")[1].label, "D-002")
            found = project.check()
            self.assertEqual(len(found), 1, found)
            self.assertTrue(found[0].startswith("warning records vesta/decisions/D-001.md:"))
            self.assertIn("now labelled D-002", found[0])
            self.assertEqual(project.run("check")[0], 0)

    def test_two_records_with_one_label_are_an_error_that_names_relabel(self):
        with Project() as project:
            project.put(decision("D-005", "0000000a"))
            project.put(decision("D-005", "0000000b"), name="D-005-theirs")
            found = errors(project.check())
            self.assertTrue(any("relabel decisions --one D-005@0000000b" in line for line in found), found)
            self.assertEqual(project.run("check")[0], 1)

    def test_one_internal_id_on_two_records_is_an_error(self):
        with Project() as project:
            project.put(decision("D-001", "0000000a"))
            project.put(decision("D-002", "0000000a"))
            found = project.check()
            self.assertEqual(len(found), 1, found)
            self.assertIn("an internal id belongs to one record", found[0])

    def test_numbered_labels_sort_by_number(self):
        with Project() as project:
            for label, uid in (("D-1000", "0000000a"), ("D-999", "0000000b"), ("D-010", "0000000c")):
                project.put(decision(label, uid))
            self.assertEqual([record.label for record in project.store().list()], ["D-010", "D-999", "D-1000"])
            _, out, _ = project.run("index")
            self.assertLess(out.index("D-999"), out.index("D-1000"))
            self.assertEqual(project.store().next_id("x")[1], "D-1001")


if __name__ == "__main__":
    unittest.main()
