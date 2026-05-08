import mafia.settings.base as base

DEBUG = base.env.bool("DJANGO_DEBUG", default=True)
INSTALLED_APPS = [*base.INSTALLED_APPS]
MIDDLEWARE = [*base.MIDDLEWARE]
INTERNAL_IPS = ["127.0.0.1"]
SERVE_STATIC_LOCALLY = True

if DEBUG:
    INSTALLED_APPS.append("debug_toolbar")
    MIDDLEWARE = [
        "debug_toolbar.middleware.DebugToolbarMiddleware",
        *MIDDLEWARE,
    ]


def __getattr__(name):
    return getattr(base, name)
