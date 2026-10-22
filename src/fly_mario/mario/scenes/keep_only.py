"""Keep only the listed object types; remove every other enemy and pickup. Works for any registered object."""
from fly_mario import registry
from fly_mario.mario import ram as R


class KeepOnly:
    name = "keep_only"
    label = "Keep only"
    description = "Keeps the chosen object types and switches off every other enemy and pickup; terrain stays."
    params = [{"key": "types", "label": "Object types to keep", "type": "object_types", "default": []}]

    def _apply(self, env, p):
        keep = set(p.get("types", []))
        plugins = registry.list_plugins("objects")
        unknown = keep - set(plugins)
        if unknown:
            raise ValueError(f"keep_only: unknown object types {sorted(unknown)}")
        facts = env.facts
        keep_bytes = [b for n in keep if plugins[n].kind == "enemy" for b in facts["objects"][n]["types"]]
        R.sweep_enemies(env, facts, keep_bytes + facts["objects"]["non_enemy"]["types"])   # also enemies no plug-in knows about; lifts stay
        for name, plugin in plugins.items():
            if name not in keep:
                plugin.remove(env)                       # pickups; a no-op for terrain

    def on_reset(self, env, p):
        self._apply(env, p)

    def on_frame(self, env, p):
        self._apply(env, p)


PLUGIN = KeepOnly()
