import django.contrib.auth
import django.db
import django.test

import game.models

User = django.contrib.auth.get_user_model()


class GameSessionTest(django.test.TestCase):
    def test_create_game_session(self):
        session = game.models.GameSession.objects.create()
        self.assertEqual(session.round, 0)


class ParticipantUniqueTest(django.test.TestCase):
    def test_unique_together(self):
        user = User.objects.create_user(username="p1")
        session = game.models.GameSession.objects.create()

        game.models.Participant.objects.create(session=session, user=user)

        with self.assertRaises(django.db.IntegrityError):
            game.models.Participant.objects.create(session=session, user=user)
