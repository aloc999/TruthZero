import time

_start_time = time.monotonic()


def get_startup_time() -> float:
    return time.monotonic() - _start_time


_lazy_modules = {}


def lazy_import(module_name: str):
    if module_name in _lazy_modules:
        return _lazy_modules[module_name]

    import importlib
    module = importlib.import_module(module_name)
    _lazy_modules[module_name] = module
    return module


def preload_essentials():
    essential = [
        "truthzero.config",
        "truthzero.agent",
    ]
    for mod in essential:
        try:
            lazy_import(mod)
        except Exception:
            pass
