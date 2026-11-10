"""Shared by every test module: puts the engine on the import path and names the fixed folders."""
import importlib.util
import os
import sys

TESTS = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.dirname(TESTS)
REPO = os.path.dirname(ENGINE)
DATA = os.path.join(TESTS, "data")

if ENGINE not in sys.path:
    sys.path.insert(0, ENGINE)


def glue(*parts):
    """Join parts at run time, so a test can build a string its own source must not hold."""
    return "".join(parts)


def tool(name):
    """Load tools/<name>.py as a module."""
    spec = importlib.util.spec_from_file_location("tool_" + name, os.path.join(REPO, "tools", name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read(path):
    """A file's text with LF line endings, whatever the checkout wrote."""
    with open(path, encoding="utf-8", newline="") as handle:
        return handle.read().replace("\r\n", "\n")


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
