__all__ = ("NightWsTests",)


from django.contrib.auth import get_user_model
from django.test import TestCase
from fakeredis import FakeRedis

import game.constants
import game.models
import game.redis_store
import game.services.night_ws


class NightWsTests(TestCase):
    def setUp(self):
        self.fake_redis = FakeRedis(decode_responses=True)
        game.redis_store.redis_client = self.fake_redis

    def test_doctor_cannot_heal_same_target_twice(self):
        user_model = get_user_model()
        doctor_user = user_model.objects.create_user("doctor_u", password="x")
        target_user = user_model.objects.create_user("target_u", password="x")
        session = game.models.GameSession.objects.create(
            slug="nightws1",
            phase=game.constants.PHASE_NIGHT,
            status="active",
            max_players=4,
        )
        game.models.Participant.objects.create(
            session=session,
            user=doctor_user,
            role=game.constants.ROLE_DOCTOR,
            is_alive=True,
        )
        target = game.models.Participant.objects.create(
            session=session,
            user=target_user,
            role=game.constants.ROLE_CIVILIAN,
            is_alive=True,
        )
        session.doctor_last_healed = target
        session.save(update_fields=["doctor_last_healed"])

        ok, payload = game.services.night_ws.set_heal_target_from_ws(
            str(session.pk),
            doctor_user.pk,
            str(target.pk),
        )

        self.assertFalse(ok)
        self.assertEqual(payload.get("code"), "doctor_same_target_twice")
        self.assertIn("две ночи подряд", payload.get("message", ""))

    def test_night_action_rejected_outside_night_phase(self):
        user_model = get_user_model()
        sheriff_user = user_model.objects.create_user(
            "sheriff_u",
            password="x",
        )
        target_user = user_model.objects.create_user("target2_u", password="x")
        session = game.models.GameSession.objects.create(
            slug="nightws2",
            phase=game.constants.PHASE_DAY_DISCUSSION,
            status="active",
            max_players=4,
        )
        game.models.Participant.objects.create(
            session=session,
            user=sheriff_user,
            role=game.constants.ROLE_SHERIFF,
            is_alive=True,
        )
        target = game.models.Participant.objects.create(
            session=session,
            user=target_user,
            role=game.constants.ROLE_CIVILIAN,
            is_alive=True,
        )

        ok, payload = game.services.night_ws.set_night_action_from_ws(
            str(session.pk),
            sheriff_user.pk,
            "check",
            str(target.pk),
        )

        self.assertFalse(ok)
        self.assertEqual(payload.get("code"), "wrong_phase")
        self.assertIn("недоступно", payload.get("message", ""))

    def test_active_roles_can_save_night_actions(self):
        user_model = get_user_model()
        mafia_user = user_model.objects.create_user("mafia_u", password="x")
        doctor_user = user_model.objects.create_user("doctor2_u", password="x")
        sheriff_user = user_model.objects.create_user(
            "sheriff2_u",
            password="x",
        )
        civilian_user = user_model.objects.create_user(
            "civilian_u",
            password="x",
        )
        session = game.models.GameSession.objects.create(
            slug="nightws3",
            phase=game.constants.PHASE_NIGHT,
            status="active",
            max_players=4,
        )
        mafia = game.models.Participant.objects.create(
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
        game.models.Participant.objects.create(
            session=session,
            user=sheriff_user,
            role=game.constants.ROLE_SHERIFF,
            is_alive=True,
        )
        civilian = game.models.Participant.objects.create(
            session=session,
            user=civilian_user,
            role=game.constants.ROLE_CIVILIAN,
            is_alive=True,
        )

        ok_kill, payload_kill = (
            game.services.night_ws.set_night_action_from_ws(
                str(session.pk),
                mafia_user.pk,
                "kill",
                str(civilian.pk),
            )
        )
        ok_heal, payload_heal = (
            game.services.night_ws.set_night_action_from_ws(
                str(session.pk),
                doctor_user.pk,
                "heal",
                str(mafia.pk),
            )
        )
        ok_check, payload_check = (
            game.services.night_ws.set_night_action_from_ws(
                str(session.pk),
                sheriff_user.pk,
                "check",
                str(mafia.pk),
            )
        )

        self.assertTrue(ok_kill, payload_kill)
        self.assertTrue(ok_heal, payload_heal)
        self.assertTrue(ok_check, payload_check)
        self.assertEqual(
            game.redis_store.get_and_clear_night_kill_target(str(session.pk)),
            civilian.pk,
        )
        self.assertEqual(
            game.redis_store.get_and_clear_night_heal_target(str(session.pk)),
            mafia.pk,
        )
        self.assertEqual(
            game.redis_store.get_and_clear_night_check_target(str(session.pk)),
            mafia.pk,
        )
