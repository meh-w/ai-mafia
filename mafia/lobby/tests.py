import django.contrib.auth
import django.test
import django.urls

import game.constants
import game.models


@django.test.override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class LobbyListViewTests(django.test.TestCase):
    def setUp(self):
        user_model = django.contrib.auth.get_user_model()
        self.user = user_model.objects.create_user("viewer", password="x")
        self.client.force_login(self.user)

    def test_room_with_free_slots_shows_join_cta(self):
        session = game.models.GameSession.objects.create(
            slug="joinme",
            status="lobby",
            phase=game.constants.PHASE_LOBBY,
            max_players=4,
        )
        owner = django.contrib.auth.get_user_model().objects.create_user(
            "owner",
            password="x",
        )
        game.models.Participant.objects.create(session=session, user=owner)

        response = self.client.get(django.urls.reverse("lobby:lobby_list"))

        self.assertContains(response, "Ввести код")
        self.assertContains(
            response,
            f"{django.urls.reverse('lobby:join')}?code=joinme",
        )

    def test_full_room_shows_disabled_cta(self):
        session = game.models.GameSession.objects.create(
            slug="fullroom",
            status="lobby",
            phase=game.constants.PHASE_LOBBY,
            max_players=4,
        )
        user_model = django.contrib.auth.get_user_model()
        for idx in range(4):
            user = user_model.objects.create_user(f"p{idx}", password="x")
            game.models.Participant.objects.create(session=session, user=user)

        response = self.client.get(django.urls.reverse("lobby:lobby_list"))

        self.assertContains(response, "Комната заполнена")
        self.assertContains(response, "Недоступно")

    def test_join_page_prefills_code_from_query(self):
        response = self.client.get(
            f"{django.urls.reverse('lobby:join')}?code=abcd1234",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="abcd1234"')

    def test_finished_rooms_are_hidden_from_lobby_list(self):
        finished = game.models.GameSession.objects.create(
            slug="finishedroom",
            status="finished",
            phase=game.constants.PHASE_FINISHED,
            max_players=4,
        )
        owner = django.contrib.auth.get_user_model().objects.create_user(
            "owner_finished",
            password="x",
        )
        game.models.Participant.objects.create(session=finished, user=owner)

        response = self.client.get(django.urls.reverse("lobby:lobby_list"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "finishedroom")
