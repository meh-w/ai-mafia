import django.conf


def site_ui(request):
    return {
        "debug": django.conf.settings.DEBUG,
    }
