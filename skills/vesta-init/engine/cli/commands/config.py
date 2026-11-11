"""`config [set <key> <value>]`: what can be changed about how Vesta behaves, and a change to the
project's configuration drafted as a proposal, so that nobody edits the file by hand."""
from __future__ import annotations

from cli import args, manifest
from cli.commands import propose
from kernel import yamlsubset
from kernel.errors import Refusal, SubsetError, UsageError
from model.abstractions import KindError
from model import config as configuration
from proposals import blocks
from proposals import proposal as proposals
from session import pending, settings

# The command builds its change from what it reads, so it runs alone (cli/main.py).
ALONE = True
RULE = "vesta/INTERNALS.md, How changes are made"
TARGET = "vesta.yml"


def _data(context):
    try:
        return yamlsubset.read(context.config_text, configuration.PATH)
    except SubsetError as error:
        raise UsageError("%s does not read: %s" % (configuration.PATH, error))


def _listed(context):
    data = _data(context)
    context.write("# What can be changed")
    context.write()
    context.write("## On this machine")
    context.write()
    context.write("These are this person's own. `setting <name> <answer>` changes one at once; `setting <name>` says what each answer means.")
    context.write()
    for name in settings.names(context):
        try:
            resolved = settings.resolve(context, name)
            context.write("- `%s`: %s Now %s." % (name, resolved.setting.asks, settings.said(resolved)))
        except UsageError as error:
            context.write("- `%s`: %s" % (name, error))
    context.write()
    context.write("## For the project")
    context.write()
    context.write("These hold for everyone who works in the project. `config set <key> <value>` drafts the change as a proposal; it takes effect once the owner approves it.")
    context.write()
    for key, means, shape in configuration.offered(data):
        value, named = configuration.held(data, key)
        context.write("- `%s`: %s. Now %s. Takes %s." % (key, means, "`%s`" % configuration.shown(value) if named else "not set", configuration.takes(shape)))
    context.write()
    context.write("Any other key of %s is changed by a proposal filled by hand: `propose config --target %s --source %s`. "
                  "The agent-instruction file that points at Vesta is chosen with `/vesta-init`." % (configuration.PATH, TARGET, propose.OWNER))
    return 0


def _waiting(context, key, value):
    """([the labels of waiting proposals that set a key to this value], [(label, value) of those that set it to another])."""
    same, others = [], []
    for store, record in pending.pending(context):
        if record.get(pending.KIND) != "config":
            continue
        try:
            values = blocks.dotted_block(proposals.Proposal(store, record).change())
        except KindError:
            continue  # one still being filled by hand sets nothing yet
        if key in values and values[key] == value:
            same.append(record.label)
        elif key in values:
            others.append((record.label, values[key]))
    return same, others


def _set(context, key, text):
    data = _data(context)
    known = dict((name, (means, shape)) for name, means, shape in configuration.offered(data))
    if key not in known:
        raise UsageError("`%s` is not a key `config set` changes; `config` lists the ones it does, and says how any other is changed" % " ".join(key.split())[:80])
    means, shape = known[key]
    try:
        value = configuration.parsed(shape, text)
    except ValueError as error:
        raise UsageError("`%s` takes %s; `%s` is not that" % (key, error, " ".join(text.split())[:80]))
    old, named = configuration.held(data, key)
    if named and old == value:
        context.write("`%s` is `%s` already, so no proposal was drafted." % (key, configuration.shown(value)))
        return 0
    before = configuration.problems(context.config_text, manifest.known())
    here = data
    parts = key.split(".")
    for position, part in enumerate(parts[:-1]):
        if part in here and not isinstance(here[part], dict):
            raise UsageError("`%s` in %s is not a mapping, so `%s` cannot be set under it; `check` says what is wrong with the file"
                             % (".".join(parts[:position + 1]), configuration.PATH, key))
        here = here.setdefault(part, {})
    here[parts[-1]] = value
    same, others = _waiting(context, key, value)
    if same:
        context.write("%s already proposes `%s` as `%s` and is waiting for the owner, so no second proposal was drafted. `proposals %s` prints it."
                      % (same[0], key, configuration.shown(value), same[0]))
        return 0
    after = configuration.problems(yamlsubset.write(data), manifest.known())
    worse = [message for _, message in after if message not in [said for _, said in before]]
    if worse:
        raise Refusal("with `%s` set to `%s` the configuration would not be in order: %s. No proposal was drafted."
                      % (key, configuration.shown(value), "; ".join(worse)), RULE)
    line = "%s: %s" % (key, yamlsubset.write({"value": value}).split(":", 1)[1].strip())
    was = "`%s`" % configuration.shown(old) if named else "not set"
    body = "\n".join([
        "# Set `%s` to `%s` in the configuration" % (key, configuration.shown(value)),
        "",
        "## Why",
        "The owner asked for it directly on %s. `%s` is %s. It was %s when this was drafted." % (context.clock.today(), key, means, was),
        "",
        "## Counter-case",
        "It holds for everyone who works in this project, from the next command on. Setting it back is another proposal.",
        "",
        "## %s" % proposals.CHANGE,
        "```%s" % blocks.SET,
        line,
        "```",
        "",
    ])
    label, path = propose.begin(context, ["config", "--target", TARGET, "--source", propose.OWNER], lambda text="": None, body)
    context.write("Drafted %s: `%s` would go from %s to `%s`. It is in %s; nothing has changed yet." % (label, key, was, configuration.shown(value), path))
    for label_, other in others:
        context.write("%s is also waiting and would set `%s` to `%s`. Of two that are applied, the one applied last stands: tell the owner, "
                      "and have the one not wanted rejected." % (label_, key, configuration.shown(other)))
    context.write("**Do:** Put it to the owner in one sentence: what would change and for whom. On a yes that names it, run `apply %s`; "
                  "on a no, `reject %s --reason -` with their reason. `proposals %s` prints it in full." % (label, label, label))
    return 0


def run(context, arguments):
    words, _ = args.split(arguments, takes=True)
    if not words:
        return _listed(context)
    if words[0] != "set" or len(words) != 3:
        raise UsageError("`config` takes nothing, or `set <key> <value>`, as `config set engagement quiet`")
    return _set(context, words[1], words[2])
