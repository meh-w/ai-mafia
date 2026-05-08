import django.contrib.auth
import django.test

import game.constants
import game.models
import game.services.voting


class VotingTieTests(django.test.TestCase):
    def test_day_vote_tie_skips_exclusion(self):
        user_model = django.contrib.auth.get_user_model()
        voter_1_user = user_model.objects.create_user(
            "voter_1",
            password="x",
        )
        voter_2_user = user_model.objects.create_user(
            "voter_2",
            password="x",
        )
        target_1_user = user_model.objects.create_user(
            "target_1",
            password="x",
        )
        target_2_user = user_model.objects.create_user(
            "target_2",
            password="x",
        )
        session = game.models.GameSession.objects.create(
            slug="vote-tie-room",
            phase=game.constants.PHASE_DAY_VOTE,
            status="active",
            round=1,
            max_players=4,
        )
        voter_1 = game.models.Participant.objects.create(
            session=session,
            user=voter_1_user,
            role=game.constants.ROLE_CIVILIAN,
            is_alive=True,
        )
        voter_2 = game.models.Participant.objects.create(
            session=session,
            user=voter_2_user,
            role=game.constants.ROLE_CIVILIAN,
            is_alive=True,
        )
        target_1 = game.models.Participant.objects.create(
            session=session,
            user=target_1_user,
            role=game.constants.ROLE_CIVILIAN,
            is_alive=True,
        )
        target_2 = game.models.Participant.objects.create(
            session=session,
            user=target_2_user,
            role=game.constants.ROLE_CIVILIAN,
            is_alive=True,
        )
        game.models.VoteRecord.objects.create(
            session=session,
            round=1,
            voter=voter_1,
            target=target_1,
            kind=game.models.VoteRecord.KIND_NATURAL,
            artifact_key="",
        )
        game.models.VoteRecord.objects.create(
            session=session,
            round=1,
            voter=voter_2,
            target=target_2,
            kind=game.models.VoteRecord.KIND_NATURAL,
            artifact_key="",
        )

        result = game.services.voting.apply_day_vote_exclusion(session, 1)
        target_1.refresh_from_db()
        target_2.refresh_from_db()

        self.assertIsNone(result["excluded_id"])
        self.assertTrue(result["skipped_due_to_tie"])
        self.assertTrue(target_1.is_alive)
        self.assertTrue(target_2.is_alive)
