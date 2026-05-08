import importlib
import os

import mafia.settings.base as base

if os.environ.get("DJANGO_ENVIRONMENT", "local") == "production":
    _active = importlib.import_module("mafia.settings.production")
else:
    _active = importlib.import_module("mafia.settings.local")


def __getattr__(name):
    try:
        return getattr(_active, name)
    except AttributeError:
        return getattr(base, name)


def __dir__():
    names = {n for n in dir(base) if n.isupper()}
    names |= {n for n in dir(_active) if n.isupper()}
    return sorted(names)
