import django.urls

import lobby.views

app_name = "lobby"

urlpatterns = [
    django.urls.path(
        "lobby/",
        lobby.views.LobbyListView.as_view(),
        name="lobby_list",
    ),
    django.urls.path(
        "lobby/create/",
        lobby.views.SessionCreateView.as_view(),
        name="session_create",
    ),
    django.urls.path(
        "lobby/join/",
        lobby.views.SessionJoinView.as_view(),
        name="join",
    ),
]
