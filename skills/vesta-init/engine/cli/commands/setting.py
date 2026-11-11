"""`setting [<name> [<answer> | --clear]]`: what is chosen on this machine and not for the project."""
from __future__ import annotations

from cli import args
from kernel.errors import UsageError
from session import settings

CLEAR = "--clear"


def _all(context):
    context.write("# Settings on this machine")
    context.write()
    context.write("These are this person's and this machine's: kept in %s, which is not committed. The project's own are in vesta/vesta.yml." % settings.PATH)
    context.write()
    for name in settings.names(context):
        resolved = settings.resolve(context, name)
        context.write("- `%s`: %s %s." % (name, resolved.setting.asks, settings.said(resolved)))
    context.write()
    context.write("`setting <name>` prints one with what each answer means. `setting <name> <answer>` keeps an answer; `setting <name> %s` forgets it." % CLEAR)
    return 0


def _one(context, name):
    resolved = settings.resolve(context, name)
    context.write("# Setting `%s`" % name)
    context.write()
    context.write(resolved.setting.asks)
    context.write()
    for value, line in resolved.setting.options:
        fallen, why = resolved.setting.effect(context, value)
        context.write("- `%s`: %s%s" % (value, line, "" if fallen == value else " Here it would act as `%s`, because %s." % (fallen, why)))
    context.write()
    context.write("As it stands: %s." % settings.said(resolved))
    context.write("`setting %s <answer>` keeps an answer; `setting %s %s` forgets it." % (name, name, CLEAR))
    return 0


def run(context, arguments):
    words, options = args.split(arguments, flags=(CLEAR,), takes=True)
    if not words:
        if options:
            raise UsageError("`%s` takes the name of a setting, as `setting <name> %s`" % (CLEAR, CLEAR))
        return _all(context)
    name = words[0]
    settings.member(context, name)
    if CLEAR in options:
        if len(words) != 1:
            raise UsageError("`setting %s %s` takes no answer" % (name, CLEAR))
        had = settings.clear(context, name)
        context.write("%s As it stands: %s." % ("The answer chosen for `%s` was forgotten." % name if had else "Nothing was chosen for `%s`, so nothing was changed." % name,
                                               settings.said(settings.resolve(context, name))))
        return 0
    if len(words) == 1:
        return _one(context, name)
    if len(words) != 2:
        raise UsageError("`setting` takes a name and one answer, as `setting %s <answer>`" % name)
    settings.choose(context, name, words[1])
    resolved = settings.resolve(context, name)
    context.write("Kept for `%s`: %s." % (name, settings.said(resolved)))
    for line in resolved.setting.after(context, words[1]):
        context.write(line)
    return 0
