import django.contrib.auth
import django.test

import game.constants
import game.forms
import game.models
import lobby.forms


class FormStylingTests(django.test.TestCase):
    def test_lobby_forms_apply_bootstrap_classes(self):
        join_form = lobby.forms.SessionJoinForm()
        create_form = lobby.forms.SessionCreateForm()

        self.assertEqual(
            join_form.fields["code"].widget.attrs.get("class"),
            "form-control",
        )
        self.assertEqual(
            create_form.fields["max_players"].widget.attrs.get("class"),
            "form-select",
        )

    def test_vote_form_excludes_voter_from_targets(self):
        user_model = django.contrib.auth.get_user_model()
        voter_user = user_model.objects.create_user("voter", password="x")
        target_user = user_model.objects.create_user("target", password="x")
        session = game.models.GameSession.objects.create(
            slug="vote-form-room",
            phase=game.constants.PHASE_DAY_VOTE,
            status="active",
            max_players=4,
            round=1,
        )
        voter = game.models.Participant.objects.create(
            session=session,
            user=voter_user,
            role=game.constants.ROLE_CIVILIAN,
            is_alive=True,
        )
        target = game.models.Participant.objects.create(
            session=session,
            user=target_user,
            role=game.constants.ROLE_CIVILIAN,
            is_alive=True,
        )

        form = game.forms.VoteForm(session=session, voter=voter)

        self.assertEqual(
            form.fields["target"].widget.attrs.get("class"),
            "form-select",
        )
        self.assertNotIn(voter, form.fields["target"].queryset)
        self.assertIn(target, form.fields["target"].queryset)
