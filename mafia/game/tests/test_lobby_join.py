__all__ = ("LobbyJoinTests",)


import django.contrib.auth
import django.test
import django.urls

import game.constants
import game.models


@django.test.override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class LobbyJoinTests(django.test.TestCase):
    def test_invalid_room_code_returns_form_error(self):
        user_model = django.contrib.auth.get_user_model()
        user = user_model.objects.create_user("player", password="x")
        self.client.force_login(user)

        response = self.client.post(
            django.urls.reverse("lobby:join"),
            data={"code": "missing-room"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Комната не найдена или уже недоступна.")

    def test_valid_room_code_redirects_to_game(self):
        user_model = django.contrib.auth.get_user_model()
        user = user_model.objects.create_user("player", password="x")
        owner = user_model.objects.create_user("owner", password="x")
        session = game.models.GameSession.objects.create(
            slug="roomcode",
            phase=game.constants.PHASE_LOBBY,
            max_players=7,
        )
        game.models.Participant.objects.create(
            session=session,
            user=owner,
        )
        self.client.force_login(user)

        response = self.client.post(
            django.urls.reverse("lobby:join"),
            data={"code": "roomcode"},
        )

        self.assertRedirects(
            response,
            django.urls.reverse("game:play", args=[session.pk]),
        )
