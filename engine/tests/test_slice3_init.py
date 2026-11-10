import json
import os
import unittest

import support
import fixtures
from fixtures import BODY, Project, decision
from kernel.shipped import digest
from stores import walks

VERBATIM = os.path.join(support.DATA, "verbatim")
TEMPLATES = os.path.join(support.ENGINE, "templates")

TREE = sorted([
    "vesta/.gitignore", "vesta/.manifest.json", "vesta/INTERNALS.md", "vesta/README.md", "vesta/language.md", "vesta/vesta.yml",
    "vesta/decisions/README.md", "vesta/decisions/SCHEMA.md",
    "vesta/observations/README.md", "vesta/observations/SCHEMA.md",
    "vesta/proposals/README.md", "vesta/proposals/SCHEMA.md",
    "vesta/walks/README.md", "vesta/walks/start.md", "vesta/walks/close.md", "vesta/walks/learn.md",
    "vesta/log/admissions.md", "vesta/log/admitted.json", "vesta/log/consultations.jsonl",
])
FOLDERS = sorted([
    "vesta/.state", "vesta/decisions", "vesta/observations", "vesta/observations/open", "vesta/observations/archive", "vesta/proposals",
    "vesta/walks", "vesta/log", "vesta/log/proposals", "vesta/log/passes",
])
GOVERNED = sorted([
    "vesta/vesta.yml", "vesta/language.md", "vesta/walks/start.md", "vesta/walks/close.md", "vesta/walks/learn.md",
    "vesta/decisions/SCHEMA.md", "vesta/observations/SCHEMA.md", "vesta/proposals/SCHEMA.md",
])


class Init(unittest.TestCase):
    def test_init_in_an_empty_folder_creates_exactly_the_tree(self):
        with Project(init=True) as project:
            self.assertEqual(sorted(project.files()), TREE)
            self.assertEqual(project.folders(), FOLDERS)

    def test_check_passes_on_a_fresh_folder(self):
        with Project(init=True) as project:
            code, out, _ = project.run("check")
            self.assertEqual(code, 0, out)
            self.assertEqual(project.check(), [])
            for name in project.config["checks"]["run"]:
                self.assertIn("- `%s`: " % name, out)

    def test_the_shipped_configuration_is_written_as_shipped(self):
        with Project() as bare:
            os.remove(bare.path("vesta/vesta.yml"))
            import shutil
            shutil.rmtree(bare.path("vesta"))
            self.assertEqual(bare.run("init")[0], 0)
            self.assertEqual(bare.read("vesta/vesta.yml"), support.read(os.path.join(VERBATIM, "vesta.yml")))

    def test_init_refuses_where_the_configuration_exists_and_changes_nothing(self):
        with Project(init=True) as project:
            project.write("src/main.txt", "the project's own file\n")
            before = project.files()
            code, out, _ = project.run("init")
            self.assertEqual(code, 3)
            self.assertIn("already set up", out)
            self.assertIn("The rule is in vesta/INTERNALS.md", out)
            self.assertEqual(project.files(), before)

    def test_init_writes_nothing_outside_the_folder(self):
        with Project() as bare:
            import shutil
            shutil.rmtree(bare.path("vesta"))
            bare.write("README.md", "mine\n")
            bare.write("src/main.txt", "mine\n")
            self.assertEqual(bare.run("init")[0], 0)
            outside = dict((path, text) for path, text in bare.files().items() if not path.startswith("vesta/"))
            self.assertEqual(outside, {"README.md": "mine\n", "src/main.txt": "mine\n"})

    def test_the_fingerprints_of_the_governed_files_and_of_the_shipped_text_are_recorded(self):
        with Project(init=True) as project:
            admitted = json.loads(project.read("vesta/log/admitted.json"))
            self.assertEqual(sorted(admitted), GOVERNED)
            for path in GOVERNED:
                self.assertEqual(admitted[path], digest(project.read(path)), path)
            manifest = json.loads(project.read("vesta/.manifest.json"))
            self.assertEqual(sorted("vesta/" + name for name in manifest), [path for path in TREE if path not in ("vesta/.manifest.json", "vesta/log/admitted.json")])
            self.assertEqual(manifest["language.md"], digest(support.read(os.path.join(VERBATIM, "language.md"))))

    def test_the_setup_answers(self):
        with Project() as bare:
            import shutil
            shutil.rmtree(bare.path("vesta"))
            self.assertEqual(bare.run("init")[0], 0)
            shipped = bare.read("vesta/vesta.yml")
            code, out, _ = bare.run("init", "--owner", 'Ada "the owner" O\'Neil: lead', "--engagement", "active")
            self.assertEqual(code, 0, out)
            config = bare.context().config
            self.assertEqual((config.owner, config.engagement, config.pointer_file), ('Ada "the owner" O\'Neil: lead', "active", ""))
            changed = [pair for pair in zip(shipped.split("\n"), bare.read("vesta/vesta.yml").split("\n")) if pair[0] != pair[1]]
            self.assertEqual(len(changed), 2, changed)
            self.assertEqual(json.loads(bare.read("vesta/log/admitted.json"))["vesta/vesta.yml"], digest(bare.read("vesta/vesta.yml")))
            code, out, _ = bare.run("init", "--pointer-file", "./AGENTS.md")
            self.assertEqual(code, 3)
            self.assertIn("does not hold the Vesta block yet", out)
            bare.write("AGENTS.md", support.read(os.path.join(TEMPLATES, "pointer-block.md")))
            self.assertEqual(bare.run("init", "--pointer-file", "./AGENTS.md")[0], 0)
            self.assertEqual(bare.context().config.pointer_file, "AGENTS.md")
            self.assertEqual(bare.run("init", "--engagement", "loud")[0], 2)
            self.assertEqual(bare.run("init", "--pointer-file", "../elsewhere.md")[0], 2)
            bare.write("vesta/log/admissions.md", bare.read("vesta/log/admissions.md") + "- 2026-01-05 · P-001@0000000a · add · D-001@0000000b · approved by A. Reviewer · evidence 0\n")
            code, out, _ = bare.run("init", "--engagement", "quiet")
            self.assertEqual(code, 3)
            self.assertIn("through a `config` proposal", out)
            self.assertEqual(bare.context().config.engagement, "active")

    def test_doctor_reports_what_it_runs_on(self):
        with Project(init=True) as project:
            code, out, _ = project.run("doctor")
            self.assertEqual(code, 0)
            for phrase in ("- Python: 3.", "- Project root: " + project.root, "- Changed files are found by: mtime", "- Pointer file: none", "- Engagement: standard"):
                self.assertIn(phrase, out)


class ShippedText(unittest.TestCase):
    def shipped(self, name):
        return support.read(os.path.join(TEMPLATES, *name.split("/")))

    def test_the_shipped_files_equal_the_verbatim_blocks(self):
        pairs = [("vesta/language.md", "language.md"), ("vesta/walks/start.md", "walks-start.md"), ("vesta/walks/close.md", "walks-close.md"),
                 ("vesta/walks/learn.md", "walks-learn.md"), ("pointer-block.md", "pointer-block.md"), ("vesta/vesta.yml", "vesta.yml")]
        for shipped, verbatim in pairs:
            self.assertEqual(self.shipped(shipped), support.read(os.path.join(VERBATIM, verbatim)), shipped)
        for example in ("observation-example-1.md",):
            self.assertIn(support.read(os.path.join(VERBATIM, example)), self.shipped("vesta/observations/SCHEMA.md"))

    def test_the_lengths_the_shipped_files_are_held_to(self):
        def lines(name):
            return len(self.shipped(name).rstrip("\n").split("\n"))
        self.assertLess(lines("vesta/language.md"), 110)
        self.assertLess(lines("vesta/README.md"), 40)
        self.assertLessEqual(lines("pointer-block.md"), 15)
        self.assertLess(lines("vesta/walks/README.md"), 40)
        for store in ("decisions", "observations", "proposals"):
            self.assertLess(lines("vesta/%s/README.md" % store), 30, store)

    def test_the_user_readme_uses_none_of_the_words_of_the_mechanism(self):
        text = self.shipped("vesta/README.md").lower()
        import re
        for word in ("latch", "walk", "row", "lens", "bar", "ladder", "sweep", "mark", "bundle", "checkpoint", "observation"):
            self.assertIsNone(re.search(r"\b%ss?\b" % word, text), word)

    def test_the_internals_glossary_holds_every_term_a_user_may_meet(self):
        text = self.shipped("vesta/INTERNALS.md")
        for term in ("owner", "session", "pass", "window", "ledger", "register", "decision", "observation", "proposal", "anchor", "index",
                     "governed", "scope", "warrant", "falsifier", "revisit trigger", "probe", "recheck", "successor", "load", "latch",
                     "checkpoint", "walk", "row", "lens", "counterfactual", "seed", "brief", "mark", "jot", "steer", "should-have-loaded",
                     "off-map", "bundle", "close report", "shape", "group", "bar", "ladder", "apply", "disposition", "hold", "archive",
                     "check", "residue", "standing cost"):
            self.assertIn("\n| %s |" % term, text, term)

    def test_the_neutrality_check_passes_over_a_generated_folder(self):
        neutrality = support.tool("neutrality")
        private = neutrality.default_terms(support.REPO)
        terms = neutrality.read_terms(private if os.path.isfile(private) else os.path.join(support.DATA, "sample-terms.txt"))
        with Project(init=True) as project:
            hits, read = neutrality.scan(project.root, terms)
            self.assertEqual(hits, [])
            self.assertGreaterEqual(read, len(TREE))

    def test_every_skill_file_has_its_frontmatter_and_sections_and_is_short(self):
        skills = os.path.join(support.REPO, "skills")
        for name in sorted(os.listdir(skills)):
            path = os.path.join(skills, name, "SKILL.md")
            if not os.path.isfile(path):
                continue
            text = support.read(path)
            self.assertTrue(text.startswith("---\nname: %s\ndescription: " % name), name)
            for heading in ("## When to run", "## What it does", "## Procedure", "## Do / Don't", "## What this does not guarantee"):
                self.assertIn("\n%s\n" % heading, text, "%s lacks %s" % (name, heading))
            self.assertLess(len(text.rstrip("\n").split("\n")), 120, name)


class Levels(unittest.TestCase):
    def test_one_five_and_eight_lenses_at_the_three_levels_across_start_and_close(self):
        with Project(init=True) as project:
            tree = project.context().tree
            start, close = walks.read(tree, "vesta/walks/start.md"), walks.read(tree, "vesta/walks/close.md")
            totals = {}
            for level in walks.LEVELS:
                shown = [lens["lens"] for lens in start.lenses_at(level)] + [lens["lens"] for lens in close.lenses_at(level)]
                totals[level] = len(shown)
                for walk in (start, close):
                    for lens in walk.lenses:
                        above = walks.LEVELS.index(lens["level"]) > walks.LEVELS.index(level)
                        self.assertEqual(lens["lens"] not in shown, above, "%s at %s" % (lens["lens"], level))
            self.assertEqual(totals, {"quiet": 1, "standard": 5, "active": 8})
            self.assertEqual([len(start.rows_at(level)) for level in walks.LEVELS], [0, 1, 1])
            self.assertIsNotNone(close.prose("Choices"))
            learn = walks.read(tree, "vesta/walks/learn.md")
            self.assertEqual((learn.rows, learn.lenses), ([], []))
            for name in ("Shapes", "Bars", "Ladder"):
                self.assertTrue(learn.prose(name))


class PointerBlock(unittest.TestCase):
    def test_with_no_pointer_file_the_check_passes(self):
        with Project(init=True) as project:
            self.assertEqual(project.check(), [])

    def test_set_and_present_passes_removed_or_changed_fails(self):
        block = support.read(os.path.join(TEMPLATES, "pointer-block.md"))
        with Project(init=True) as project:
            project.write("AGENTS.md", "# Agents\n\nThe project's own text.\n\n" + block + "\nMore of the project's text.\n")
            self.assertEqual(project.run("init", "--pointer-file", "AGENTS.md")[0], 0)
            self.assertEqual(project.check(), [])
            project.write("AGENTS.md", "# Agents\n\nThe project's own text.\n")
            found = project.check()
            self.assertEqual(len(found), 1, found)
            self.assertIn("error pointer-block AGENTS.md:1 the Vesta block is not in this file", found[0])
            project.write("AGENTS.md", block.replace("settled decisions", "decisions"))
            self.assertIn("differs from the one this engine ships", project.check()[0])
            project.write("AGENTS.md", block.replace("## Vesta\n", "## Vesta\n" + "\n" * 4))
            self.assertEqual(len(project.check()), 2)
            os.remove(project.path("AGENTS.md"))
            self.assertIn("no file is there", project.check()[0])


class Language(unittest.TestCase):
    def test_a_tell_is_flagged_in_a_when_line_and_ignored_elsewhere(self):
        with Project(init=True) as project:
            project.put(decision(when="sending anything to a client, for now"))
            project.admit("vesta/decisions/D-001.md")
            found = project.check()
            self.assertEqual(len(found), 1, found)
            self.assertTrue(found[0].startswith("warning language vesta/decisions/D-001.md:"))
            self.assertIn('the `when` line holds "for now"', found[0])
            quiet = [
                decision(when="sending anything to a client"),
                decision(when="sending `for now` anything"),
                decision(when="sending a platform now-cast to a client; a reform nowhere stated; before nowadays"),
            ]
            body = BODY.replace("Reports are drafted over several days.", "For now, reports are drafted over several days; we decided this recently.")
            for fields in quiet:
                project.put(fields, body)
                project.admit("vesta/decisions/D-001.md")
                self.assertEqual(project.check(), [], fields["when"])

    def test_the_title_the_why_line_and_the_payload_section_are_read(self):
        with Project(init=True) as project:
            body = BODY.replace("# Every figure", "# Currently every figure").replace("Every figure is checked against", "As discussed, every figure is checked against")
            project.put(decision(why="the latest draft goes out"), body)
            project.admit("vesta/decisions/D-001.md")
            text = "\n".join(project.check())
            for phrase in ('the title holds "currently"', 'the `why` line holds "the latest"', 'the Decision section holds "as discussed"'):
                self.assertIn(phrase, text)
            self.assertEqual(len(project.check()), 3)

    def test_the_phrases_come_from_the_projects_own_writing_rules(self):
        from checks import language
        phrases = language.tells(support.read(os.path.join(VERBATIM, "language.md")))
        self.assertIn("we decided", phrases)
        self.assertIn("the old one", phrases)
        self.assertEqual(len(phrases), 20)
        self.assertEqual(language.found_in("D-004 replaced the old one", ["the old one"]), ["the old one"])
        self.assertEqual(language.found_in("see TO-DO list", ["to do"]), [])


ROW = "| start-02 | the task changes how a release is cut | `scripts/release*` | `docs/releasing.md` | read the checklist | standard | seed |\n"


class WalksAndLinks(unittest.TestCase):
    def with_row(self, project, row, path="vesta/walks/start.md"):
        text = project.read(path)
        marker = "| start-01 |"
        index = text.index(marker)
        end = text.index("\n", index) + 1
        project.write(path, text[:end] + row + text[end:])
        project.admit(path)
        return project.check()

    def test_a_well_formed_row_passes_and_its_missing_consult_path_is_a_warning(self):
        with Project(init=True) as project:
            found = self.with_row(project, ROW)
            self.assertEqual(len(found), 1, found)
            self.assertIn("warning links vesta/walks/start.md:", found[0])
            self.assertIn("consults `docs/releasing.md`, which is not in the project", found[0])
            project.write("docs/releasing.md", "# Releasing\n")
            self.assertEqual(project.check(), [])

    def test_each_row_rule(self):
        cases = [
            (ROW.replace("start-02", "start-01"), "the row id `start-01` occurs twice"),
            (ROW.replace("start-02", "close-02"), "has the form `start-NN`"),
            (ROW.replace("`scripts/release*`", "scripts/release*"), "`fires-on` of the row `start-02` is `—`, or globs in backticks"),
            (ROW.replace("`docs/releasing.md`", "`docs/a.md` and `docs/b.md`"), "consults more than one thing"),
            (ROW.replace("read the checklist", "check the claim at the source before building on it"), "owe the same act"),
            (ROW.replace("| standard |", "| loud |"), "`level` of the row `start-02` is one of quiet, standard, active"),
            (ROW.replace("| seed |", "| P-404 |"), "`origin` of the row `start-02` is `P-404`"),
            (ROW.replace("| read the checklist ", "|  "), "has no `owed act`"),
            (ROW.replace("| seed |", "| seed"), "a table row closes with `|`"),
            (ROW.replace("| seed |", "| seed | extra |"), "a table row has 8 cells; the header has 7"),
        ]
        for row, phrase in cases:
            with Project(init=True) as project:
                project.write("docs/releasing.md", "x\n")
                project.write("docs/a.md", "x\n")
                project.write("docs/b.md", "x\n")
                found = [line for line in self.with_row(project, row) if line.startswith("error walks ")]
                self.assertEqual(len(found), 1, "%s: %s" % (phrase, found))
                self.assertIn(phrase, found[0])

    def test_a_lens_name_is_used_once_across_the_walk_files_and_an_origin_resolves(self):
        with Project(init=True) as project:
            text = project.read("vesta/walks/close.md")
            line = "| said-before | Which part repeats? | Is it written down where it would be found? | standard | P-003@0000000c |\n"
            index = text.index("| friction |")
            project.write("vesta/walks/close.md", text[:index] + line + text[index:])
            project.admit("vesta/walks/close.md")
            found = project.check()
            self.assertEqual(len(found), 2, found)
            self.assertIn("the lens `said-before` is also in vesta/walks/start.md", found[0])
            self.assertIn("`origin` of the lens `said-before` is `P-003@0000000c`", found[1])
            project.write("vesta/log/proposals/P-003.md", "decided\n")
            self.assertEqual(len(project.check()), 1)

    def test_a_missing_walk_file_and_a_changed_header(self):
        with Project(init=True) as project:
            os.remove(project.path("vesta/walks/learn.md"))
            project.write("vesta/walks/start.md", project.read("vesta/walks/start.md").replace("| id | fires-when |", "| name | fires-when |"))
            text = "\n".join(line for line in project.check() if line.startswith("error walks"))
            self.assertIn("the walk file of `learn` is missing", text)
            self.assertIn("the Rows table has the columns name, fires-when", text)

    def test_links_a_reference_that_resolves_nowhere_is_an_error_and_a_missing_scope_a_warning(self):
        with Project(init=True) as project:
            project.put(decision("D-001", "0000000a", related=["D-009@0000000f"], scopes=["reports/"]))
            project.admit("vesta/decisions/D-001.md")
            found = project.check()
            self.assertEqual(len(found), 2, found)
            self.assertIn("error links vesta/decisions/D-001.md:", found[0])
            self.assertIn("`related` names D-009@0000000f, which is not a record", found[0])
            self.assertIn("warning links", found[1])
            self.assertIn("`scopes` names `reports/`, which is not in the project", found[1])
            project.write("reports/q1.md", "x\n")
            self.assertEqual(len(project.check()), 1)


class AfterTheReview(unittest.TestCase):
    """What the review of this slice found, each held by a test."""

    def test_init_refuses_to_write_over_files_already_in_the_folder(self):
        with Project() as bare:
            import shutil
            shutil.rmtree(bare.path("vesta"))
            bare.write("vesta/README.md", "MY OWN README\n")
            bare.write("vesta/decisions/README.md", "mine\n")
            before = bare.files()
            code, out, _ = bare.run("init")
            self.assertEqual(code, 3)
            self.assertIn("vesta/README.md, vesta/decisions/README.md", out)
            self.assertEqual(bare.files(), before)

    def test_an_interrupted_init_is_undone_by_the_next_command_and_can_be_run_again(self):
        from kernel import tree as trees
        with Project() as bare:
            import shutil
            shutil.rmtree(bare.path("vesta"))
            real = trees.DiskTree.write
            calls = []

            def failing(self, path, text):
                calls.append(path)
                if len(calls) == 6:
                    raise OSError("the disk is full")
                return real(self, path, text)

            trees.DiskTree.write = failing
            try:
                code, _, err = bare.run("init")
            finally:
                trees.DiskTree.write = real
            self.assertEqual(code, 2)
            self.assertIn("could not be read or written", err)
            self.assertTrue(os.path.isfile(bare.path("vesta/.state/journal.json")))
            code, out, _ = bare.run("init")
            self.assertEqual(code, 0, out)
            self.assertIn("put back as they were", out)
            self.assertEqual(sorted(bare.files()), TREE)

    def test_a_copy_of_the_engine_that_is_not_whole_writes_nothing(self):
        from cli import build
        from kernel import shipped
        self.assertEqual(build.shipped().damage(), [])
        self.assertEqual(json.loads(self_read(os.path.join(TEMPLATES, "shipped.json"))), build.shipped().fingerprints())
        with Project() as bare:
            import shutil
            shutil.rmtree(bare.path("vesta"))
            copy = bare.path("engine-copy")
            shutil.copytree(TEMPLATES, os.path.join(copy, "templates"))
            os.remove(os.path.join(copy, "templates", "vesta", "walks", "close.md"))
            support.write(os.path.join(copy, "templates", "vesta", "language.md"), "changed\n")
            real = build.shipped
            build.shipped = lambda: shipped.Shipped(copy)
            try:
                code, _, err = bare.run("init")
            finally:
                build.shipped = real
            self.assertEqual(code, 2)
            self.assertIn("this copy of the engine is not whole", err)
            self.assertIn("templates/vesta/walks/close.md is missing", err)
            self.assertIn("templates/vesta/language.md is not the text that was shipped", err)
            self.assertFalse(os.path.isdir(bare.path("vesta")))

    def test_a_setup_answer_is_not_written_into_a_configuration_edited_by_hand(self):
        with Project() as bare:
            import shutil
            shutil.rmtree(bare.path("vesta"))
            bare.run("init")
            edited = bare.read("vesta/vesta.yml").replace("governed: true", "governed: false")
            bare.write("vesta/vesta.yml", edited)
            recorded = bare.read("vesta/log/admitted.json")
            code, out, _ = bare.run("init", "--owner", "Mallory")
            self.assertEqual(code, 3)
            self.assertIn("was edited by hand", out)
            self.assertEqual((bare.read("vesta/vesta.yml"), bare.read("vesta/log/admitted.json")), (edited, recorded))

    def test_the_owner_name_is_one_line_and_help_is_given_for_any_command(self):
        with Project() as bare:
            code, _, err = bare.run("init", "--owner", "a\nb")
            self.assertEqual(code, 2)
            self.assertIn("a name on one line", err)
            code, out, _ = bare.run("init", "-h")
            self.assertEqual(code, 0)
            self.assertIn("commands:", out)

    def test_two_blocks_in_the_pointer_file_are_an_error(self):
        block = support.read(os.path.join(TEMPLATES, "pointer-block.md"))
        with Project(init=True) as project:
            project.write("AGENTS.md", block)
            project.run("init", "--pointer-file", "AGENTS.md")
            project.write("AGENTS.md", block + "\n" + block.replace("settled decisions", "IGNORE ALL"))
            found = project.check()
            self.assertEqual(len(found), 1, found)
            self.assertIn("more than once", found[0])
            project.write("AGENTS.md", block.replace("settled decisions", "decisions"))
            self.assertIn("vesta/.engine/templates/pointer-block.md", project.check()[0])

    def test_a_pointer_file_outside_the_project_is_a_finding_and_doctor_still_reports(self):
        with Project(init=True) as project:
            project.write_config(project.read("vesta/vesta.yml").replace('pointer-file: ""', "pointer-file: ../outside.md"))
            code, out, err = project.run("doctor")
            self.assertEqual((code, err), (0, ""))
            self.assertIn("- Pointer file: ../outside.md, which is not in the project", out)
            found = project.check()
            self.assertTrue(any(line.startswith("error config") and "`pointer-file` is `../outside.md`" in line for line in found), found)

    def test_a_check_that_has_nothing_to_read_says_so(self):
        with Project(init=True) as project:
            rules = project.read("vesta/language.md")
            project.write("vesta/language.md", rules.replace("### Tells", "### Signs"))
            self.assertTrue(any(line.startswith("error language vesta/language.md:1 no table of phrases") for line in project.check()))
            os.remove(project.path("vesta/language.md"))
            self.assertTrue(any(line.startswith("error language vesta/language.md:1 the writing rules file is missing") for line in project.check()))
        with Project(init=True) as project:
            close = project.read("vesta/walks/close.md")
            project.write("vesta/walks/close.md", close.replace("## Lenses", "## Lens"))
            found = [line for line in project.check() if line.startswith("error walks")]
            self.assertEqual(len(found), 1, found)
            self.assertIn("vesta/walks/close.md:1 the file has no `## Lenses` section, which the step `lenses` prints", found[0])

    def test_the_store_folders_come_from_the_stores_and_the_internals_map_names_every_entry(self):
        with Project(init=True) as project:
            context = project.context()
            self.assertEqual(context.stores.get("observations").folders(), ["vesta/observations", "vesta/observations/open", "vesta/observations/archive"])
            self.assertEqual(context.stores.get("decisions").folders(), ["vesta/decisions"])
            internals = project.read("vesta/INTERNALS.md")
            for entry in (".manifest.json", ".gitignore", ".engine/", ".state/", "log/admitted.json"):
                self.assertIn("| `%s` |" % entry, internals)
            self.assertIn("setup answers", internals)

    def test_the_init_skill_discloses_its_three_limits(self):
        text = " ".join(self_read(os.path.join(support.REPO, "skills", "vesta-init", "SKILL.md")).split())
        for phrase in ("Nothing forces an agent to run Vesta", "carried a step out honestly", "cannot tell whether the owner approved it", "don't add a second block", "starting on a new line"):
            self.assertIn(phrase, text)


def self_read(path):
    return support.read(path)


if __name__ == "__main__":
    unittest.main()
