"""What a proposal's target names: a store, a record, a trigger, or a file of the project's `vesta/` folder."""
from __future__ import annotations

from kernel import ids
from kernel import tree as trees
from matchers import index
from model import config as configuration
from model.abstractions import KindError, OUTCOME, DISPOSITION

LANGUAGE = "vesta/language.md"


def store(context, target):
    """A store that holds records a proposal may add to: any but the proposals and the observations."""
    found = context.stores.get(target.strip())
    if found is None:
        raise KindError("`%s` is not a store of this project; the stores are: %s" % (target, ", ".join(context.stores.names())))
    if found.type.life_field(OUTCOME) or found.type.life_field(DISPOSITION):
        raise KindError("the store `%s` takes no record through a proposal" % found.name)
    return found


def record(context, target, accepted=False):
    """(store, record) for a record a proposal changes. With `accepted`, one that is in force."""
    found = context.stores.resolve(target.strip()) if target.strip() else None
    if found is None:
        raise KindError("`%s` names no record; `index --all` lists the records" % target)
    if found[0].type.life_field(OUTCOME) or found[0].type.life_field(DISPOSITION):
        raise KindError("%s is in the store `%s`, whose records no proposal changes" % (found[1].label, found[0].name))
    if accepted and not found[0].type.is_accepted(found[1]):
        raise KindError("%s is not in force, so no proposal changes it" % found[1].label)
    return found


def records(context, target):
    """[(store, record)] for a target that names two or more records of one store, separated by commas."""
    names = [name.strip() for name in target.split(",") if name.strip()]
    found = [record(context, name, accepted=True) for name in names]
    if len(set(item[1].uid for item in found)) < 2:
        raise KindError("a merge names two or more records, separated by commas")
    if len(set(item[0].name for item in found)) > 1:
        raise KindError("the records of a merge are all in one store")
    return found


def trigger(context, target):
    """(store, record, trigger id) for `<record>/t1`, where that trigger is live."""
    name, trigger_id = ids.split_trigger_ref(target.strip())
    if trigger_id is None:
        raise KindError("`%s` does not name a trigger; a trigger is named `<record>/t1`" % target)
    found_store, found = record(context, name, accepted=True)
    live = [item.get("id") for item in index.live_triggers(found_store, found)]
    if trigger_id not in live:
        raise KindError("%s has no live trigger `%s`; its live triggers are: %s" % (found.label, trigger_id, ", ".join(str(item) for item in live) or "none"))
    return found_store, found, trigger_id


def path(context, target):
    """A file under `vesta/`, named with or without the folder's own name in front."""
    text = target.strip().replace("\\", "/")
    text = text if text.startswith(trees.HOME) else trees.HOME + text
    try:
        return trees.inside_home(text)
    except ValueError:
        raise KindError("`%s` is not a file of the project's vesta/ folder" % target)


def walk_file(context, target):
    """(path, checkpoint) for a target that names a walk file."""
    wanted = path(context, target)
    for checkpoint in context.config.checkpoints.values():
        if checkpoint.walk == wanted:
            if not context.tree.is_file(wanted):
                raise KindError("%s is missing" % wanted)
            return wanted, checkpoint
    walks = ", ".join(sorted(checkpoint.walk for checkpoint in context.config.checkpoints.values()))
    raise KindError("`%s` is not a walk file; the walk files are: %s" % (target, walks or "none"))


def schema_file(context, target):
    wanted = path(context, target)
    files = sorted(settings.path + "/SCHEMA.md" for settings in context.config.stores.values())
    if wanted not in files or not context.tree.is_file(wanted):
        raise KindError("`%s` is not a store's SCHEMA.md; those are: %s" % (target, ", ".join(files)))
    return wanted


def config_file(context, target):
    if path(context, target) != configuration.PATH:
        raise KindError("a `config` proposal's target is `vesta.yml`")
    return configuration.PATH


def prose_file(context, target):
    """The writing rules, or a walk file."""
    wanted = path(context, target)
    if wanted == LANGUAGE and context.tree.is_file(wanted):
        return wanted, None
    return walk_file(context, target)
