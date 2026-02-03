import importlib

class ScriptProxy:
    def __init__(self, node, module_name: str):
        self.node = node
        self._module_name = module_name
        self._module = importlib.import_module(module_name)

    def _call(self, name: str, *args):
        fn = getattr(self._module, name, None)
        if callable(fn):
            return fn(self, *args)
        return None

    def _ready(self):
        return self._call("_ready")

    def _process(self, delta):
        return self._call("_process", delta)

    def _input(self, event):
        return self._call("_input", event)

    def __getattr__(self, name):
        module = object.__getattribute__(self, "_module")
        if hasattr(module, name):
            return getattr(module, name)
        raise AttributeError(name)


def _resolve_script_class(module):
    script_cls = getattr(module, "SCRIPT_CLASS", None) or getattr(module, "__script_class__", None)
    if isinstance(script_cls, str):
        script_cls = getattr(module, script_cls, None)
    if isinstance(script_cls, type):
        return script_cls
    return None


def load_script(module_name: str, node):
    module = importlib.import_module(module_name)
    script_cls = _resolve_script_class(module)
    if script_cls:
        return script_cls(node)
    return ScriptProxy(node, module_name)


def get_script_module(script) -> str | None:
    if isinstance(script, str):
        return script
    if hasattr(script, "_module_name"):
        return getattr(script, "_module_name")
    return getattr(getattr(script, "__class__", None), "__module__", None)