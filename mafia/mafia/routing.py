from django.urls import re_path

from game import consumers as game_consumers

websocket_urlpatterns = [
    re_path(
        r"ws/game/(?P<session_id>[0-9a-fA-F-]{36})/$",
        game_consumers.GameConsumer.as_asgi(),
    ),
]
