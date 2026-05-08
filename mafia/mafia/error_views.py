import django.shortcuts


def handler403(request, exception=None):
    return django.shortcuts.render(
        request,
        "403.html",
        status=403,
    )


def handler404(request, exception=None):
    return django.shortcuts.render(
        request,
        "404.html",
        status=404,
    )


def handler500(request):
    return django.shortcuts.render(
        request,
        "500.html",
        status=500,
    )
