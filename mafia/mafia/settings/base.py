from datetime import timedelta
import importlib
from pathlib import Path
from urllib.parse import urlparse
import warnings

import django.core.exceptions
from django.utils.translation import gettext_lazy as _
import environ

env = environ.Env()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

environ.Env.read_env(BASE_DIR.parent / ".env")

SECRET_KEY = env.str("DJANGO_SECRET_KEY", default="fake-secret")

DEBUG = env.bool("DJANGO_DEBUG", default=False)

ALLOWED_HOSTS = env.list(
    "DJANGO_ALLOWED_HOSTS",
    default=["127.0.0.1", "localhost"],
)

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "homepage.apps.HomepageConfig",
    "users.apps.UsersConfig",
    "lobby.apps.LobbyConfig",
    "game.apps.GameConfig",
    "channels",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "mafia.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "mafia.context_processors.site_ui",
            ],
        },
    },
]

ASGI_APPLICATION = "mafia.asgi.application"

WSGI_APPLICATION = "mafia.wsgi.application"

DATABASES = {
    "default": env.db(),
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation." "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]

LANGUAGE_CODE = "ru"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

LANGUAGES = [
    ("ru", _("Russian")),
    ("en", _("English")),
]

LOCALE_PATHS = [
    BASE_DIR / "game" / "locale",
]

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static_dev"]
STATIC_ROOT = BASE_DIR / "static"
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = env.str("REDIS_URL", default="redis://127.0.0.1:6379/0")


def _parse_redis_hosts(url: str):
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 6379
    return [(host, port)]


def _channel_layers_setting():
    mode = env.str("DJANGO_CHANNEL_LAYER", default="auto").lower()
    if mode not in ("auto", "redis", "memory"):
        raise django.core.exceptions.ImproperlyConfigured(
            "DJANGO_CHANNEL_LAYER must be one of: auto, redis, memory",
        )

    if mode == "memory":
        return {
            "default": {
                "BACKEND": "channels.layers.InMemoryChannelLayer",
            },
        }

    try:
        importlib.import_module("channels_redis")
    except ImportError as exc:
        if mode == "redis":
            raise django.core.exceptions.ImproperlyConfigured(
                "DJANGO_CHANNEL_LAYER=redis but channels-redis is not "
                "installed. Run: pip install -r requirements/dev.txt",
            ) from exc

        warnings.warn(
            "Пакет channels-redis не найден; используется "
            "InMemoryChannelLayer (один процесс разработки). Для Redis и "
            "прод-подобного режима: pip install -r requirements/dev.txt и "
            "запуск Redis (см. docs/DOCKER.md).",
            RuntimeWarning,
            stacklevel=2,
        )
        return {
            "default": {
                "BACKEND": "channels.layers.InMemoryChannelLayer",
            },
        }

    return {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": _parse_redis_hosts(REDIS_URL),
            },
        },
    }


CHANNEL_LAYERS = _channel_layers_setting()

CELERY_BROKER_URL = env.str("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = env.str("CELERY_RESULT_BACKEND", default=REDIS_URL)
CELERY_TIMEZONE = TIME_ZONE
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

PHASE_SCAN_INTERVAL_SEC = env.int("PHASE_SCAN_INTERVAL_SEC", default=5)
CHECKPOINT_INTERVAL_SEC = env.int("CHECKPOINT_INTERVAL_SEC", default=60)

CELERY_BEAT_SCHEDULE = {
    "tick-due-phases": {
        "task": "game.tasks.tick_due_phases",
        "schedule": timedelta(seconds=PHASE_SCAN_INTERVAL_SEC),
    },
    "checkpoint-snapshot": {
        "task": "game.tasks.checkpoint_snapshot",
        "schedule": timedelta(seconds=CHECKPOINT_INTERVAL_SEC),
    },
}

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "lobby:lobby_list"
LOGOUT_REDIRECT_URL = "homepage:main"
