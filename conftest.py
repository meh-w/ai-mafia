import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mafia.settings")
django.setup()
