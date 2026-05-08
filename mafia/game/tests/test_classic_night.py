__all__ = ("ClassicNightTests",)


from django.contrib.auth import get_user_model
from django.test import override_settings, TestCase
from fakeredis import FakeRedis

import game.constants
import game.models
import game.redis_store
import game.services.classic_night


@override_settings(
    CHANNEL_LAYERS={
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    },
)
class ClassicNightTests(TestCase):
    def setUp(self):
        self.fake_redis = FakeRedis(decode_responses=True)
        game.redis_store.redis_client = self.fake_redis

    def test_resolve_night_allows_skipped_actions(self):
        user_model = get_user_model()
        session = game.models.GameSession.objects.create(
            slug="nightskip",
            phase=game.constants.PHASE_NIGHT,
            round=1,
            balance_config={"default_phase_seconds": 60},
        )
        mafia_user = user_model.objects.create_user("mafia_u", password="x")
        doctor_user = user_model.objects.create_user("doctor_u", password="x")
        sheriff_user = user_model.objects.create_user(
            "sheriff_u",
            password="x",
        )
        civil_user = user_model.objects.create_user("civil_u", password="x")
        game.models.Participant.objects.create(
            session=session,
            user=mafia_user,
            role=game.constants.ROLE_MAFIA,
            is_alive=True,
        )
        game.models.Participant.objects.create(
            session=session,
            user=doctor_user,
            role=game.constants.ROLE_DOCTOR,
            is_alive=True,
        )
        sheriff = game.models.Participant.objects.create(
            session=session,
            user=sheriff_user,
            role=game.constants.ROLE_SHERIFF,
            is_alive=True,
            sheriff_checks=[],
        )
        civil = game.models.Participant.objects.create(
            session=session,
            user=civil_user,
            role=game.constants.ROLE_CIVILIAN,
            is_alive=True,
        )

        detail = game.services.classic_night.resolve_classic_night(session, 1)

        self.assertIsNone(detail["kill_attempt"])
        self.assertIsNone(detail["heal"])
        self.assertIsNone(detail["check"])
        self.assertIsNone(detail["killed"])
        sheriff.refresh_from_db()
        civil.refresh_from_db()
        self.assertEqual(sheriff.sheriff_checks, [])
        self.assertTrue(civil.is_alive)
