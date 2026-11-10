import ast
import importlib.util
import os
import unittest

import support

# 02-architecture: a package imports only from packages with a lower number, and from itself.
LAYERS = {
    "kernel": 1,
    "model": 2,
    "stores": 3,
    "adapters": 3,
    "matchers": 4,
    "session": 5,
    "steps": 6,
    "proposals": 7,
    "checks": 8,
    "migrations": 9,
    "cli": 10,
}
ONLY = {"adapters": {"kernel", "model"}}


def imports(path):
    """Yield (line, top-level module name) for every import of a source file."""
    tree = ast.parse(support.read(path), path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                yield node.lineno, None
            elif node.module:
                yield node.lineno, node.module.split(".")[0]


OUTSIDE = ("tests", "templates", "__pycache__")


def dynamic_imports(path):
    """Yield the lines of a source file that import by name at run time."""
    for node in ast.walk(ast.parse(support.read(path), path)):
        if isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            if name in ("import_module", "__import__"):
                yield node.lineno


def third_party(path):
    found = []
    for line, module in imports(path):
        if module is None or module in LAYERS:
            continue
        spec = importlib.util.find_spec(module)
        origin = (spec.origin or "") if spec else ""
        if spec is None or "site-packages" in origin or "dist-packages" in origin:
            found.append("%s:%d imports %s" % (path, line, module))
    return found


def sources():
    for package in sorted(LAYERS):
        for folder, names, leaves in os.walk(os.path.join(support.ENGINE, package)):
            names[:] = [name for name in names if name != "__pycache__"]
            for leaf in sorted(leaves):
                if leaf.endswith(".py"):
                    yield package, os.path.join(folder, leaf)


def violations(package, path):
    found = []
    for line, module in imports(path):
        try:
            shown = os.path.relpath(path, support.ENGINE)
        except ValueError:  # on another drive
            shown = path
        where = "%s:%d" % (shown, line)
        if module is None:
            found.append(where + " a relative import; name the package")
        elif module in LAYERS:
            if module == package:
                continue
            if LAYERS[module] >= LAYERS[package]:
                found.append("%s %s imports %s against the layer order" % (where, package, module))
            elif package in ONLY and module not in ONLY[package]:
                found.append("%s %s imports %s; it may import only %s" % (where, package, module, sorted(ONLY[package])))
        else:
            spec = importlib.util.find_spec(module)
            origin = (spec.origin or "") if spec else ""
            if spec is None or "site-packages" in origin or "dist-packages" in origin:
                found.append("%s imports %s, which is not in the standard library" % (where, module))
    return found


class Layers(unittest.TestCase):
    def test_every_package_of_the_layout_exists(self):
        for package in LAYERS:
            self.assertTrue(os.path.isfile(os.path.join(support.ENGINE, package, "__init__.py")), package)

    def test_no_import_goes_against_the_layer_order_or_outside_the_standard_library(self):
        found = []
        for package, path in sources():
            found.extend(violations(package, path))
        self.assertEqual(found, [])

    def test_the_engine_folder_holds_no_package_outside_the_layer_order(self):
        for name in sorted(os.listdir(support.ENGINE)):
            if os.path.isdir(os.path.join(support.ENGINE, name)) and name not in OUTSIDE:
                self.assertIn(name, LAYERS, "engine/%s is not a package of the layer order" % name)

    def test_only_the_command_line_imports_a_module_by_name(self):
        found = []
        for package, path in sources():
            if package != "cli":
                found.extend("%s:%d" % (path, line) for line in dynamic_imports(path))
        self.assertEqual(found, [])

    def test_the_entry_point_and_the_tools_import_only_the_standard_library(self):
        paths = [os.path.join(support.ENGINE, "__main__.py")]
        tools = os.path.join(support.REPO, "tools")
        paths += [os.path.join(tools, leaf) for leaf in sorted(os.listdir(tools)) if leaf.endswith(".py")]
        found = []
        for path in paths:
            found.extend(third_party(path))
        self.assertEqual(found, [])

    def test_the_test_itself_fails_on_an_import_against_the_order(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            cases = [
                ("kernel", "from model import context\n", "against the layer order"),
                ("stores", "import adapters.git\n", "against the layer order"),
                ("adapters", "from stores import files\n", "against the layer order"),
                ("steps", "def f():\n    import proposals.apply\n", "against the layer order"),
                ("model", "from . import context\n", "relative import"),
                ("kernel", "import " + support.glue("ya", "ml") + "_not_installed_here\n", "standard library"),
            ]
            for package, source, expected in cases:
                path = os.path.join(folder, "case.py")
                support.write(path, source)
                found = violations(package, path)
                self.assertEqual(len(found), 1, source)
                self.assertIn(expected, found[0])
            support.write(os.path.join(folder, "dynamic.py"), "import importlib\nm = importlib.import_module('cli.manifest')\nn = __import__('model.context')\n")
            self.assertEqual(list(dynamic_imports(os.path.join(folder, "dynamic.py"))), [2, 3])
            support.write(os.path.join(folder, "fine.py"), "import os\nfrom kernel import tree\nimport model.context\n")
            self.assertEqual(violations("stores", os.path.join(folder, "fine.py")), [])


if __name__ == "__main__":
    unittest.main()
