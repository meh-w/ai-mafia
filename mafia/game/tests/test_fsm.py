__all__ = ("FSMTransitionTests",)


from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import override_settings, TestCase
import django.utils.timezone
from fakeredis import FakeRedis

from game.constants import (
    DEFAULT_LOBBY_PLAYERS,
    PHASE_DAY_DISCUSSION,
    PHASE_NIGHT,
    ROLE_CIVILIAN,
    ROLE_DOCTOR,
    ROLE_MAFIA,
    ROLE_SHERIFF,
)
from game.fsm import (
    transition,
    transition_by_deadline,
    transition_error_user_message,
)
import game.models
import game.redis_store
import game.tasks


@override_settings(
    CHANNEL_LAYERS={
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    },
)
class FSMTransitionTests(TestCase):
    def setUp(self):
        self.fake_redis = FakeRedis(decode_responses=True)
        game.redis_store.redis_client = self.fake_redis

    def test_advance_from_lobby_starts_classic(self):
        user_model = get_user_model()
        session = game.models.GameSession.objects.create(
            slug="fsmtest",
            phase="lobby",
            round=0,
            seq=0,
            balance_config={"default_phase_seconds": 60},
        )
        for i in range(DEFAULT_LOBBY_PLAYERS):
            user = user_model.objects.create_user(f"u{i}", password="x")
            game.models.Participant.objects.create(
                session=session,
                user=user,
            )
        ok, payload = transition(str(session.pk), "advance")
        self.assertTrue(ok)
        session.refresh_from_db()
        self.assertEqual(session.phase, PHASE_NIGHT)
        self.assertEqual(session.status, "active")
        self.assertEqual(session.round, 0)
        self.assertEqual(session.seq, 1)
        self.assertIn("state", payload)

    def test_transition_error_user_message_lobby_not_full(self):
        user_model = get_user_model()
        session = game.models.GameSession.objects.create(
            slug="fsmtest2",
            phase="lobby",
            round=0,
            seq=0,
            balance_config={"default_phase_seconds": 60},
            max_players=7,
        )
        user = user_model.objects.create_user("solo", password="x")
        game.models.Participant.objects.create(session=session, user=user)
        ok, payload = transition(str(session.pk), "advance")
        self.assertFalse(ok)
        msg = transition_error_user_message(payload)
        self.assertIn("1 из 7", msg)

    def test_transition_by_deadline_advances_night_to_day(self):
        user_model = get_user_model()
        session = game.models.GameSession.objects.create(
            slug="fsmdeadline1",
            phase=PHASE_NIGHT,
            status="active",
            round=0,
            seq=10,
            ends_at=django.utils.timezone.now() - timedelta(seconds=1),
            balance_config={"default_phase_seconds": 60},
            max_players=4,
        )
        players = [
            ("maf", ROLE_MAFIA),
            ("doc", ROLE_DOCTOR),
            ("shr", ROLE_SHERIFF),
            ("civ", ROLE_CIVILIAN),
        ]
        for username, role in players:
            user = user_model.objects.create_user(username, password="x")
            game.models.Participant.objects.create(
                session=session,
                user=user,
                role=role,
                is_alive=True,
            )

        transition_error = transition_by_deadline(str(session.pk))

        self.assertIsNone(transition_error)
        session.refresh_from_db()
        self.assertEqual(session.phase, PHASE_DAY_DISCUSSION)
        self.assertEqual(session.round, 1)
        self.assertEqual(session.seq, 11)
        self.assertIsNotNone(session.ends_at)

    def test_tick_due_phases_continues_if_single_session_fails(self):
        now = django.utils.timezone.now()
        s1 = game.models.GameSession.objects.create(
            slug="fsmtick1",
            phase=PHASE_NIGHT,
            status="active",
            ends_at=now - timedelta(seconds=1),
            max_players=4,
        )
        s2 = game.models.GameSession.objects.create(
            slug="fsmtick2",
            phase=PHASE_NIGHT,
            status="active",
            ends_at=now - timedelta(seconds=1),
            max_players=4,
        )
        call_results = [RuntimeError("boom"), None]

        def side_effect(_session_id):
            result = call_results.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        with mock.patch(
            "game.fsm.transition_by_deadline", side_effect=side_effect
        ) as mocked:
            game.tasks.tick_due_phases()

        called_session_ids = [call.args[0] for call in mocked.call_args_list]
        self.assertIn(str(s1.pk), called_session_ids)
        self.assertIn(str(s2.pk), called_session_ids)
