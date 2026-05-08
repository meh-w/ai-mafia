from django.conf import settings
from django.conf.urls.static import static
import django.contrib
from django.urls import include, path, re_path
from django.views.static import serve

import mafia.error_views
import users.views

urlpatterns = [
    path("admin/", django.contrib.admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path(
        "accounts/register/",
        users.views.SignupView.as_view(),
        name="register",
    ),
    path("", include("homepage.urls")),
    path("", include("lobby.urls")),
    path("", include("game.urls")),
]

if getattr(settings, "SERVE_STATIC_LOCALLY", False):
    urlpatterns += [
        re_path(
            r"^static/(?P<path>.*)$",
            serve,
            {"document_root": settings.STATICFILES_DIRS[0]},
        ),
    ]

if settings.DEBUG:
    from debug_toolbar.toolbar import debug_toolbar_urls

    urlpatterns += debug_toolbar_urls()

    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )

handler403 = mafia.error_views.handler403
handler404 = mafia.error_views.handler404
handler500 = mafia.error_views.handler500
