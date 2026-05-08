__all__ = ("AcceptanceTests",)


from django.contrib.auth import get_user_model
from django.test import TestCase

import game.constants
import game.models
import game.services.hints
import game.services.win_conditions


class AcceptanceTests(TestCase):
    def test_evaluate_win_town_when_no_mafia_alive(self):
        user_model = get_user_model()
        session = game.models.GameSession.objects.create(
            slug="win1",
            phase="day_discussion",
            round=1,
        )
        u1 = user_model.objects.create_user("a1", password="x")
        u2 = user_model.objects.create_user("a2", password="x")
        mafia_user = user_model.objects.create_user("m1", password="x")
        game.models.Participant.objects.create(
            session=session,
            user=u1,
            role=game.constants.ROLE_CIVILIAN,
            is_alive=True,
        )
        game.models.Participant.objects.create(
            session=session,
            user=u2,
            role=game.constants.ROLE_CIVILIAN,
            is_alive=True,
        )
        game.models.Participant.objects.create(
            session=session,
            user=mafia_user,
            role=game.constants.ROLE_MAFIA,
            is_alive=False,
        )
        summary = game.services.win_conditions.evaluate_win(session)
        self.assertIsNotNone(summary)
        assert summary is not None
        self.assertEqual(summary["primary"], "town")

    def test_hints_payload_when_enabled(self):
        user_model = get_user_model()
        user = user_model.objects.create_user("hintuser", password="x")
        game.models.PlayerProfile.objects.create(
            user=user,
            hints_enabled=True,
            preferred_language="en",
        )
        session = game.models.GameSession.objects.create(
            phase="lobby", round=0
        )
        participant = game.models.Participant.objects.create(
            session=session,
            user=user,
            role=game.constants.ROLE_CIVILIAN,
        )
        hint_payload = game.services.hints.build_hint_payload_for_player(
            user,
            session,
            participant,
        )
        self.assertIn("hint_body", hint_payload)
        self.assertEqual(hint_payload.get("hint_locale"), "en")

    def test_hints_disabled_empty_payload(self):
        user_model = get_user_model()
        user = user_model.objects.create_user("hintoff", password="x")
        game.models.PlayerProfile.objects.create(
            user=user,
            hints_enabled=False,
            preferred_language="ru",
        )
        session = game.models.GameSession.objects.create(
            phase="lobby", round=0
        )
        participant = game.models.Participant.objects.create(
            session=session,
            user=user,
            role=game.constants.ROLE_CIVILIAN,
        )
        hint_payload = game.services.hints.build_hint_payload_for_player(
            user,
            session,
            participant,
        )
        self.assertEqual(hint_payload, {})
