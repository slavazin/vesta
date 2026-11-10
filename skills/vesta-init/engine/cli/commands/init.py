"""`init`: scaffold `vesta/` from the shipped text and record its fingerprints.

`init [--owner <name or ->] [--engagement <level>] [--pointer-file <path>]`. The three options are
the owner's own setup answers. They may be given with the first run, or once more on a folder in which
no proposal has been decided yet; after that the configuration changes through a `config` proposal.
"""
from __future__ import annotations

import re

from cli import args, build
from kernel import tree as trees
from kernel import yamlsubset
from kernel.errors import Refusal, UsageError
from kernel.shipped import MANIFEST, digest, listing
from checks import pointer_block
from model import config as configuration
from proposals import admitted
from stores import admissions

BEFORE_SETUP = True
LOG_FOLDERS = ("vesta/log/proposals", "vesta/log/passes")
SHIPPED_BLOCK = "vesta/.engine/templates/pointer-block.md"
ANSWERS = (("--owner", "owner"), ("--engagement", "engagement"), ("--pointer-file", "pointer-file"))
RULE = "vesta/INTERNALS.md, How changes are made"
SHOWN = 5


def _answers(options):
    found = {}
    for flag, key in ANSWERS:
        if flag in options:
            found[key] = args.text(options[flag]).strip()
    if "\n" in found.get("owner", ""):
        raise UsageError("`--owner` is a name on one line")
    if "engagement" in found and found["engagement"] not in configuration.LEVELS:
        raise UsageError("`--engagement` is one of %s" % ", ".join(configuration.LEVELS))
    if found.get("pointer-file"):
        try:
            found["pointer-file"] = trees.clean(found["pointer-file"])
        except ValueError:
            raise UsageError("`--pointer-file` is a path inside the project, written from the project root")
    return found


def _set(text, answers):
    """The configuration text with the answered keys' lines replaced."""
    for key, value in answers.items():
        line = "%s: %s" % (key, yamlsubset.scalar(value))
        text, count = re.subn(r"(?m)^%s:.*$" % re.escape(key), lambda _: line, text, count=1)
        if count == 0:
            text = text.rstrip("\n") + "\n" + line + "\n"
    yamlsubset.read(text, configuration.PATH)
    return text


def _decided(tree):
    return admissions.any_decided(tree)


def _block_in_place(tree, answers):
    """Refuse a pointer file that is not there or does not hold the block: the block goes in first."""
    path = answers.get("pointer-file")
    if not path:
        return
    if not tree.is_file(path) or pointer_block.block_of(tree.read(path))[0] is None:
        raise Refusal(
            "`%s` does not hold the Vesta block yet. Add the text of %s to that file first, on lines of its own, "
            "then run this command again. Nothing was changed." % (path, SHIPPED_BLOCK), RULE,
        )


def _scaffold(root, tree, answers, out, clock):
    shipped = build.shipped()
    files = shipped.project_files()
    there = ["vesta/" + relative for relative in files + [MANIFEST[len("vesta/"):]] if tree.exists("vesta/" + relative)]
    if there:
        raise Refusal(
            "vesta/ already holds files that setting up would write over: %s. Move them away, then run `init` again. Nothing was changed."
            % ", ".join(there), RULE,
        )
    overlay = trees.Overlay(tree)
    for relative in files:
        text = shipped.project_text(relative)
        if relative == "vesta.yml" and answers:
            text = _set(text, answers)
        overlay.write("vesta/" + relative, text)
    overlay.write(MANIFEST, listing(dict((relative, digest(shipped.project_text(relative))) for relative in files)))
    context = build.context(root, out, clock, overlay)
    admitted.record(overlay, admitted.governed_paths(overlay, context.config, context.stores))
    written = overlay.commit()
    for store in context.stores.all():
        for folder in store.folders():
            tree.make_dir(folder)
    for folder in LOG_FOLDERS:
        tree.make_dir(folder)
    return len(written)


def _record(tree, answers, out):
    """Write the setup answers into a folder that is already set up."""
    if _decided(tree):
        raise Refusal(
            "the setup answers are fixed once a proposal has been decided; change `%s` through a `config` proposal. Nothing was changed."
            % "`, `".join(answers), RULE,
        )
    if admitted.read(tree).get(configuration.PATH) != digest(tree.read(configuration.PATH)):
        raise Refusal(
            "%s was edited by hand since it was last recorded, so a setup answer cannot be written into it. "
            "Run `check`: it names the two ways to settle a hand edit. Nothing was changed." % configuration.PATH, RULE,
        )
    _block_in_place(tree, answers)
    tree.write(configuration.PATH, _set(tree.read(configuration.PATH), answers))
    admitted.record(tree, [configuration.PATH])
    out.write("Recorded: %s.\n" % ", ".join("%s = %s" % (key, value or "(empty)") for key, value in answers.items()))
    return 0


def run_bare(root, arguments, out, clock):
    _, options = args.split(arguments, options=[flag for flag, _ in ANSWERS])
    answers = _answers(options)
    tree = trees.DiskTree(root)
    if tree.is_dir(configuration.PATH):
        raise UsageError("%s is a folder; it must be a file, or absent" % configuration.PATH)
    if tree.is_file(configuration.PATH):
        if not answers:
            raise Refusal("Vesta is already set up in this project (%s exists). Nothing was changed." % configuration.PATH, RULE)
        # The answers are read, changed and written back: no other command may write between.
        with tree.lock(trees.COMMAND_LOCK) as held:
            if not held:
                raise UsageError("another command is changing vesta/ at this moment; nothing was changed. Run this command again.")
            return _record(tree, answers, out)
    _block_in_place(tree, answers)
    damage = build.shipped().whole()
    if damage:
        raise UsageError(
            "this copy of the engine is not whole: %s%s. Remove vesta/.engine, copy the `engine/` folder of the vesta-init skill "
            "there again and run `init` once more. Nothing was written."
            % ("; ".join(damage[:SHOWN]), "; and %d more" % (len(damage) - SHOWN) if len(damage) > SHOWN else "")
        )
    with tree.lock(trees.COMMAND_LOCK) as held:
        if not held:
            raise UsageError("another command is changing vesta/ at this moment; nothing was changed. Run this command again.")
        count = _scaffold(root, tree, answers, out, clock)
    out.write("Created vesta/ with %d files. Nothing outside vesta/ was written.\n" % count)
    out.write("Next: record the owner's two answers with `init --owner <name or -> --engagement <quiet, standard or active>`, then run `check` and `doctor`.\n")
    return 0
