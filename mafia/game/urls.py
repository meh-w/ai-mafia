import django.urls

import game.views

app_name = "game"

urlpatterns = [
    django.urls.path(
        "game/player/settings/",
        game.views.PlayerSettingsView.as_view(),
        name="player_settings",
    ),
    django.urls.path(
        "game/<uuid:pk>/play/",
        game.views.PlayView.as_view(),
        name="play",
    ),
    django.urls.path(
        "game/<uuid:pk>/state/",
        game.views.GameStateView.as_view(),
        name="state",
    ),
    django.urls.path(
        "game/<uuid:pk>/advance/",
        game.views.PhaseAdvanceView.as_view(),
        name="phase_advance",
    ),
    django.urls.path(
        "game/<uuid:pk>/vote/",
        game.views.VoteSubmitView.as_view(),
        name="vote_submit",
    ),
    django.urls.path(
        "game/<uuid:pk>/night-action/",
        game.views.NightActionSubmitView.as_view(),
        name="night_action_submit",
    ),
    django.urls.path(
        "game/<uuid:pk>/set-traits/",
        game.views.ParticipantTraitsView.as_view(),
        name="set_traits",
    ),
]
