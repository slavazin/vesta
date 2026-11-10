"""`check`: run the checks the configuration names; print the findings, then what each does not verify."""
from __future__ import annotations

from cli import args, manifest
from kernel.finding import ERROR, Finding
from model import config as configuration


def findings(context):
    """Run every configured check this engine has, each once. Returns ([Finding], [(check id, residue)])."""
    found, residues = [], []
    for name in dict.fromkeys(context.config.checks):
        if name not in manifest.CHECKS:
            if "config" not in context.config.checks:
                found.append(Finding(ERROR, "config", configuration.PATH, 1, "`checks.run` names the check `%s`, which this engine does not have; it did not run" % name))
            continue
        check = manifest.member("checks", name)()
        found.extend(check.run(context))
        residues.append((check.id, check.residue))
    return found, residues


def _count(number, word):
    return "%d %s%s" % (number, word, "" if number == 1 else "s")


def run(context, arguments):
    args.split(arguments)
    found, residues = findings(context)
    context.write("# Check")
    context.write()
    for finding in found:
        context.write(finding.render())
    errors = len([finding for finding in found if finding.severity == ERROR])
    if found:
        context.write()
    if not residues:
        context.write("No check ran: `checks.run` in %s names none this engine has. Nothing was verified." % configuration.PATH)
        return 2
    context.write("%s, %s." % (_count(errors, "error"), _count(len(found) - errors, "warning")))
    context.write()
    context.write("What these checks do not verify:")
    for name, residue in residues:
        context.write("- `%s`: %s" % (name, residue))
    return 1 if errors else 0
