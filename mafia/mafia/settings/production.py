import mafia.settings.base as base

DEBUG = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = base.env.bool(
    "DJANGO_SECURE_SSL_REDIRECT",
    default=True,
)


def __getattr__(name):
    return getattr(base, name)
