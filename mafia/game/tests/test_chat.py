from django.contrib.auth import get_user_model
from django.test import TestCase

import game.constants
import game.models
import game.services.chat


class ChatAccessTests(TestCase):
    def test_dead_participant_cannot_send_chat_message(self):
        user_model = get_user_model()
        dead_user = user_model.objects.create_user("dead_chat", password="x")
        session = game.models.GameSession.objects.create(
            slug="deadchatroom",
            phase=game.constants.PHASE_DAY_DISCUSSION,
            status="active",
            max_players=4,
        )
        game.models.Participant.objects.create(
            session=session,
            user=dead_user,
            role=game.constants.ROLE_CIVILIAN,
            is_alive=False,
        )

        ok, payload = game.services.chat.append_public_chat_message(
            str(session.pk),
            dead_user.pk,
            "Я живой, честно",
        )

        self.assertFalse(ok)
        self.assertEqual(payload.get("code"), "forbidden")
