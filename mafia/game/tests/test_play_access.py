__all__ = ("PlayAccessTests",)


from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import override_settings, TestCase
from django.urls import reverse

import game.constants
import game.models


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class PlayAccessTests(TestCase):
    def test_non_participant_redirected_to_join_with_warning(self):
        user_model = get_user_model()
        owner = user_model.objects.create_user("owner", password="x")
        outsider = user_model.objects.create_user("outsider", password="x")
        session = game.models.GameSession.objects.create(
            slug="lockedroom",
            phase=game.constants.PHASE_LOBBY,
            max_players=7,
        )
        game.models.Participant.objects.create(session=session, user=owner)
        self.client.force_login(outsider)

        response = self.client.get(reverse("game:play", args=[session.pk]))

        self.assertRedirects(response, reverse("lobby:join"))
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(
            any(
                "Вы не состоите в этой комнате" in message for message in msgs
            ),
        )

    def test_non_participant_vote_returns_friendly_403_page(self):
        user_model = get_user_model()
        owner = user_model.objects.create_user("owner2", password="x")
        outsider = user_model.objects.create_user("outsider2", password="x")
        session = game.models.GameSession.objects.create(
            slug="lockedvote",
            phase=game.constants.PHASE_DAY_VOTE,
            status="active",
            max_players=4,
            round=1,
        )
        owner_participant = game.models.Participant.objects.create(
            session=session,
            user=owner,
            role=game.constants.ROLE_CIVILIAN,
            is_alive=True,
        )
        self.client.force_login(outsider)

        response = self.client.post(
            reverse("game:vote_submit", args=[session.pk]),
            data={"target": owner_participant.pk},
        )

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Нет доступа", status_code=403)

    def test_participant_cannot_vote_twice_in_same_round(self):
        user_model = get_user_model()
        voter_user = user_model.objects.create_user("voter_once", password="x")
        target1_user = user_model.objects.create_user(
            "target_once_1",
            password="x",
        )
        target2_user = user_model.objects.create_user(
            "target_once_2",
            password="x",
        )
        session = game.models.GameSession.objects.create(
            slug="voteonce",
            phase=game.constants.PHASE_DAY_VOTE,
            status="active",
            max_players=4,
            round=2,
        )
        voter = game.models.Participant.objects.create(
            session=session,
            user=voter_user,
            role=game.constants.ROLE_CIVILIAN,
            is_alive=True,
        )
        target1 = game.models.Participant.objects.create(
            session=session,
            user=target1_user,
            role=game.constants.ROLE_CIVILIAN,
            is_alive=True,
        )
        target2 = game.models.Participant.objects.create(
            session=session,
            user=target2_user,
            role=game.constants.ROLE_CIVILIAN,
            is_alive=True,
        )
        self.client.force_login(voter_user)

        first = self.client.post(
            reverse("game:vote_submit", args=[session.pk]),
            data={"target": target1.pk},
        )
        self.assertRedirects(first, reverse("game:play", args=[session.pk]))

        second = self.client.post(
            reverse("game:vote_submit", args=[session.pk]),
            data={"target": target2.pk},
            follow=True,
        )
        self.assertEqual(second.status_code, 200)

        votes = game.models.VoteRecord.objects.filter(
            session=session,
            round=session.round,
            voter=voter,
            kind=game.models.VoteRecord.KIND_NATURAL,
        )
        self.assertEqual(votes.count(), 1)
        self.assertEqual(votes.first().target_id, target1.pk)
        msgs = [str(m) for m in get_messages(second.wsgi_request)]
        self.assertTrue(
            any("Переголосование недоступно" in message for message in msgs),
        )

    def test_dead_participant_cannot_vote(self):
        user_model = get_user_model()
        dead_user = user_model.objects.create_user("dead_voter", password="x")
        alive_user = user_model.objects.create_user(
            "alive_target",
            password="x",
        )
        session = game.models.GameSession.objects.create(
            slug="deadvote",
            phase=game.constants.PHASE_DAY_VOTE,
            status="active",
            max_players=4,
            round=3,
        )
        dead_participant = game.models.Participant.objects.create(
            session=session,
            user=dead_user,
            role=game.constants.ROLE_CIVILIAN,
            is_alive=False,
        )
        target = game.models.Participant.objects.create(
            session=session,
            user=alive_user,
            role=game.constants.ROLE_CIVILIAN,
            is_alive=True,
        )
        self.client.force_login(dead_user)

        response = self.client.post(
            reverse("game:vote_submit", args=[session.pk]),
            data={"target": target.pk},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            game.models.VoteRecord.objects.filter(
                session=session,
                round=session.round,
                voter=dead_participant,
                kind=game.models.VoteRecord.KIND_NATURAL,
            ).exists(),
        )
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(
            any("не можете голосовать" in message for message in msgs),
        )

    def test_night_action_submit_works_like_regular_form(self):
        user_model = get_user_model()
        mafia_user = user_model.objects.create_user("mafia_form", password="x")
        target_user = user_model.objects.create_user(
            "target_form",
            password="x",
        )
        session = game.models.GameSession.objects.create(
            slug="nightform",
            phase=game.constants.PHASE_NIGHT,
            status="active",
            max_players=4,
            round=1,
        )
        game.models.Participant.objects.create(
            session=session,
            user=mafia_user,
            role=game.constants.ROLE_MAFIA,
            is_alive=True,
        )
        target = game.models.Participant.objects.create(
            session=session,
            user=target_user,
            role=game.constants.ROLE_CIVILIAN,
            is_alive=True,
        )
        self.client.force_login(mafia_user)

        with mock.patch(
            "game.services.night_ws.set_night_action_from_ws",
            return_value=(True, {}),
        ) as mocked:
            response = self.client.post(
                reverse("game:night_action_submit", args=[session.pk]),
                data={"kind": "kill", "target_id": str(target.pk)},
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        mocked.assert_called_once()
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(
            any("Ночное действие зафиксировано" in msg for msg in msgs),
        )
