import os
import random
import unittest

import support
from kernel import yamlsubset
from kernel.errors import SubsetError

FILE = "notes/a.md"


def read(text):
    return yamlsubset.read(text, FILE)


class Reads(unittest.TestCase):
    def test_every_construct_of_the_subset(self):
        text = "\n".join([
            "# a comment line",
            "plain: the rest of the line, trimmed   ",
            'quoted: "a \\"quoted\\" value with a \\\\ and a : colon"',
            'empty: ""',
            "folded: >-",
            "  first line",
            "  second line   ",
            "number: -42",
            "yes: true",
            "no: false",
            'inline: [a, "b, c", d, 7, true]',
            "none: []",
            "",
            "block:",
            "  - one",
            '  - "two: 2"',
            "maps:",
            "  - id: t1",
            "    if: >-",
            "      a long",
            "      condition",
            "    probe: \"\"",
            "  - id: t2",
            "    then: check",
            "nested:",
            "  # a comment inside",
            "  inner:",
            "    deeper:",
            "      deepest: 4",
            "back\\slash: C:\\temp\\x",
        ]).replace("back\\slash", "backslash") + "\n"
        self.assertEqual(read(text), {
            "plain": "the rest of the line, trimmed",
            "quoted": 'a "quoted" value with a \\ and a : colon',
            "empty": "",
            "folded": "first line second line",
            "number": -42,
            "yes": True,
            "no": False,
            "inline": ["a", "b, c", "d", 7, True],
            "none": [],
            "block": ["one", "two: 2"],
            "maps": [{"id": "t1", "if": "a long condition", "probe": ""}, {"id": "t2", "then": "check"}],
            "nested": {"inner": {"deeper": {"deepest": 4}}},
            "backslash": "C:\\temp\\x",
        })

    def test_types_are_exact(self):
        data = read("a: 1\nb: true\nc: \"1\"\nd: \"true\"\n")
        self.assertIs(type(data["a"]), int)
        self.assertIs(data["b"], True)
        self.assertEqual((data["c"], data["d"]), ("1", "true"))

    def test_crlf_reads_as_lf(self):
        self.assertEqual(read("a: one\r\nb: >-\r\n  x\r\n  y\r\nc: [p, q]\r\n"), {"a": "one", "b": "x y", "c": ["p", "q"]})

    def test_an_empty_document_is_an_empty_mapping(self):
        self.assertEqual(read(""), {})
        self.assertEqual(read("# only a comment\n\n"), {})

    def test_the_shipped_decision_example(self):
        text = support.read(os.path.join(support.DATA, "verbatim", "decision-example-2.md"))
        front = text.split("---\n")[1]
        data = read(front)
        self.assertEqual(data["scopes"], ["reports/", "letters/"])
        self.assertEqual(data["triggers"][0]["probe"], "missing data/figures.csv")
        self.assertTrue(data["when"].startswith("quoting a figure"))
        self.assertEqual(read(yamlsubset.write(data)), data)


REFUSED = [
    ("anchor", "a: 1\nb: &x 2\n", 2),
    ("alias", "a: 1\nb: *x\n", 2),
    ("tag", "a: !!str x\n", 1),
    ("second document", "a: 1\n---\nb: 2\n", 2),
    ("literal block", "a: 1\nb: |\n  text\n", 2),
    ("literal block, stripped", "a: |-\n  text\n", 1),
    ("folded, keeping the break", "a: >\n  text\n", 1),
    ("flow mapping", "a: {b: 1}\n", 1),
    ("single quotes", "a: 'x'\n", 1),
    ("plain scalar continued", "a: one\n  two\n", 2),
    ("key with no value at the end", "a: 1\nb:\n", 2),
    ("key with no value before a key", "a:\nb: 1\n", 1),
    ("tab in indentation", "a:\n\tb: 1\n", 2),
    ("upper-case key", "A: 1\n", 1),
    ("underscore in a key", "a_b: 1\n", 1),
    ("no space after the colon", "a:1\n", 1),
    ("three spaces of indentation", "a:\n   b: 1\n", 2),
    ("five levels", "a:\n  b:\n    c:\n      d:\n        e: 1\n", 5),
    ("colon-space in a plain value", "a: b: c\n", 1),
    ("trailing comment", "a: 1\nb: x # note\n", 2),
    ("unknown escape", 'a: "x\\n"\n', 1),
    ("unclosed quote", 'a: "x\n', 1),
    ("text after a quote", 'a: "x" y\n', 1),
    ("the same key twice", "a: 1\nb: 2\na: 3\n", 3),
    ("list in a list", "a: [b, [c]]\n", 1),
    ("unclosed inline list", "a: [b, c\n", 1),
    ("empty inline item", "a: [b, , c]\n", 1),
    ("empty folded scalar", "a: >-\nb: 1\n", 1),
    ("list item among keys", "a: 1\n- b\n", 2),
    ("key among list items", "a:\n  - b\n  c: 1\n", 3),
    ("value opening with a dash", "a: - b\n", 1),
    ("indented document", "  a: 1\n", 1),
    ("comma opener", "a: , b\n", 1),
    ("closing bracket opener", "a: ] b\n", 1),
    ("closing brace opener", "a: } b\n", 1),
    ("percent opener", "a: %b\n", 1),
    ("at opener", "a: @b\n", 1),
    ("hash opener", "a: #b\n", 1),
    ("a carriage return inside a line", "a: b\rc\n", 1),
    ("a folded line indented too far", "a: >-\n    x\n", 2),
    ("list items at the key's own indentation", "a:\n- b\n", 2),
    ("a bare dash", "a:\n  -\n", 2),
    ("four levels where three are allowed", None, 4),
]


class Refuses(unittest.TestCase):
    def test_each_refused_construct_names_file_and_line(self):
        for name, text, line in REFUSED:
            with self.assertRaises(SubsetError, msg=name) as caught:
                if text is None:
                    yamlsubset.read("a:\n  b:\n    c:\n      d: 1\n", FILE, depth=3)
                else:
                    read(text)
            self.assertEqual((caught.exception.file, caught.exception.line), (FILE, line), name)
            self.assertIn("%s:%d: " % (FILE, line), str(caught.exception))

    def test_messages_say_what_to_write(self):
        cases = [
            ("scopes:\n- reports/\n", "indent the items of the list under `scopes` by two spaces"),
            ("a:\n", "write `\"\"` for an empty text and `[]` for an empty list"),
            ("a: 1\n    b: 2\n", "a nested key goes two spaces in"),
            ("a: 'x'\n", "use double quotes"),
            ("a: |\n  x\n", "put such text in the body"),
        ]
        for text, phrase in cases:
            with self.assertRaises(SubsetError) as caught:
                read(text)
            self.assertIn(phrase, caught.exception.message, text)
            self.assertNotIn("subset", caught.exception.message)

    def test_a_byte_order_mark_is_ignored(self):
        self.assertEqual(read("\ufeffa: 1\n"), {"a": 1})

    def test_the_first_line_offset_is_added(self):
        with self.assertRaises(SubsetError) as caught:
            yamlsubset.read("a: 1\nb: *x\n", FILE, first_line=2)
        self.assertEqual(caught.exception.line, 3)


class Writes(unittest.TestCase):
    def test_a_long_string_folds_at_100_columns(self):
        value = " ".join(["word%03d" % n for n in range(40)])[:300]
        self.assertEqual(len(value), 300)
        text = yamlsubset.write({"when": value})
        lines = text.split("\n")
        self.assertEqual(lines[0], "when: >-")
        self.assertTrue(all(len(line) <= 100 for line in lines))
        self.assertTrue(any(len(line) > 90 for line in lines))
        self.assertEqual(read(text), {"when": value})

    def test_a_word_longer_than_the_width_keeps_its_own_line(self):
        value = "see " + "x" * 150 + " for more " + "y" * 20
        text = yamlsubset.write({"a": value})
        self.assertIn("\n  " + "x" * 150 + "\n", text)
        self.assertEqual(read(text), {"a": value})

    def test_named_scalar_forms(self):
        cases = [
            ("a: b", 'k: "a: b"\n'),
            ("", 'k: ""\n'),
            ("C:\\temp", "k: C:\\temp\n"),
            ('say "hi"', 'k: say "hi"\n'),
            ('"quoted"', 'k: "\\"quoted\\""\n'),
            ("back\\slash \"q\" : x", None),
            ("12", 'k: "12"\n'),
            ("true", 'k: "true"\n'),
            ("x #y", 'k: "x #y"\n'),
            ("- x", 'k: "- x"\n'),
            ("[x]", 'k: "[x]"\n'),
            (" padded ", 'k: " padded "\n'),
            ("ends:", 'k: "ends:"\n'),
            ("plain value", "k: plain value\n"),
        ]
        for value, expected in cases:
            text = yamlsubset.write({"k": value})
            if expected is not None:
                self.assertEqual(text, expected, value)
            self.assertEqual(read(text), {"k": value}, value)

    def test_a_backslash_in_a_folded_scalar_is_literal(self):
        value = "C:\\one\\two " * 12 + "end"
        text = yamlsubset.write({"k": value})
        self.assertTrue(text.startswith("k: >-\n"))
        self.assertIn("C:\\one\\two", text)
        self.assertEqual(read(text), {"k": value})

    def test_lists(self):
        self.assertEqual(yamlsubset.write({"a": []}), "a: []\n")
        self.assertEqual(yamlsubset.write({"a": ["x", "y, z", 3, "4"]}), 'a: [x, "y, z", 3, "4"]\n')
        long = ["item-number-%02d" % n for n in range(12)]
        text = yamlsubset.write({"a": long})
        self.assertEqual(text, "a:\n" + "".join("  - %s\n" % item for item in long))
        maps = {"t": [{"id": "t1", "if": "x"}, {"id": "t2", "if": "y"}]}
        self.assertEqual(yamlsubset.write(maps), "t:\n  - id: t1\n    if: x\n  - id: t2\n    if: y\n")

    def test_what_the_subset_cannot_hold_is_an_error(self):
        for value in ("a\nb", "a\rb", None, 1.5, {}, [[1]], [{}], {"a": {"b": {"c": {"d": 1}}}}):
            with self.assertRaises(ValueError, msg=repr(value)):
                yamlsubset.write({"k": value})
        for key in ("Bad_Key", "a: b", "a b", "", "a:"):
            with self.assertRaises(ValueError, msg=key):
                yamlsubset.write({key: 1})

    def test_is_canonical(self):
        self.assertTrue(yamlsubset.is_canonical("a: x\nb: [1, 2]\n"))
        self.assertFalse(yamlsubset.is_canonical('a: "x"\n'))
        self.assertFalse(yamlsubset.is_canonical("a:   x\n"))


ALPHABET = list("abcdefghij klmnop  XYZ 0123456789 :#\"'\\[]{},-|>*&!%@?=/._") + ["\t", "é", "日", "\u00a0", "\u2003", ": ", " #", "- "]


class Generated(unittest.TestCase):
    def setUp(self):
        self.random = random.Random(20260105)

    def key(self):
        r = self.random
        return r.choice("abcdefgh") + "".join(r.choice("abc123-") for _ in range(r.randint(0, 6)))

    def string(self):
        r = self.random
        kind = r.randint(0, 9)
        if kind == 0:
            return ""
        if kind == 1:
            return r.choice(["true", "false", "-7", "0", ">-", "-", "[]", "a:", "~", "null"])
        length = r.choice([1, 3, 8, 20, 60, 110, 250])
        return "".join(r.choice(ALPHABET) for _ in range(length))

    def scalar(self):
        r = self.random
        kind = r.randint(0, 5)
        if kind == 0:
            return r.randint(-1000, 1000)
        if kind == 1:
            return r.choice([True, False])
        return self.string()

    def mapping(self, depth):
        r = self.random
        result = {}
        for _ in range(r.randint(1, 5)):
            kind = r.randint(0, 9)
            if kind <= 4:
                value = self.scalar()
            elif kind == 5:
                value = [self.scalar() for _ in range(r.randint(0, 6))]
            elif kind == 6 and depth < yamlsubset.MAX_DEPTH:
                value = [self.mapping(depth + 1) if r.random() < 0.8 else self.scalar() for _ in range(r.randint(1, 3))]
            elif kind == 7 and depth < yamlsubset.MAX_DEPTH:
                value = self.mapping(depth + 1)
            else:
                value = self.string()
            result[self.key()] = value
        return result

    def test_200_mappings_round_trip_byte_for_byte(self):
        for number in range(200):
            data = self.mapping(1)
            text = yamlsubset.write(data)
            back = read(text)
            self.assertEqual(back, data, "mapping %d\n%s" % (number, text))
            self.assertEqual(self.types(back), self.types(data), number)
            self.assertEqual(yamlsubset.write(back), text, number)

    def types(self, value):
        if isinstance(value, dict):
            return dict((key, self.types(item)) for key, item in value.items())
        if isinstance(value, list):
            return [self.types(item) for item in value]
        return type(value).__name__


class InternalIds(unittest.TestCase):
    def test_an_internal_id_of_digits_only_is_written_and_read_as_text(self):
        from kernel import yamlsubset
        for value in ("00000000", "12345678", "1e345678", "1234567e", "0e000000", "deadbeef"):
            self.assertEqual(yamlsubset.read(yamlsubset.write({"uid": value}), "x")["uid"], value)


if __name__ == "__main__":
    unittest.main()
