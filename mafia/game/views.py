__all__ = (
    "PlayView",
    "GameStateView",
    "PhaseAdvanceView",
    "NightActionSubmitView",
    "VoteSubmitView",
    "PlayerSettingsView",
)


import django.contrib.auth.mixins
import django.contrib.messages
import django.core.exceptions
import django.http
import django.shortcuts
import django.views
import django.views.generic

import game.broadcasting
import game.constants
import game.forms
import game.fsm
import game.models
import game.redis_store
import game.services.hints
import game.services.night_ws
import game.services.voting

PROFILE_DEFAULTS = {"hints_enabled": True, "preferred_language": "ru"}


class PlayView(
    django.contrib.auth.mixins.LoginRequiredMixin,
    django.views.generic.DetailView,
):
    model = game.models.GameSession
    template_name = "game/play.html"
    context_object_name = "session"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        session = self.get_object()
        if not session.participants.filter(user_id=request.user.id).exists():
            django.contrib.messages.warning(
                request,
                "Вы не состоите в этой комнате. Введите код приглашения.",
            )
            return django.shortcuts.redirect("lobby:join")

        return super().dispatch(request, *args, **kwargs)

    @staticmethod
    def _get_or_create_profile(user):
        return game.models.PlayerProfile.objects.get_or_create(
            user=user,
            defaults=PROFILE_DEFAULTS,
        )

    @staticmethod
    def _build_vote_context(session, current_participant, participants):
        existing_vote = PlayView._get_existing_vote(
            session,
            current_participant,
        )
        tally = game.services.voting.tally_votes_for_round(
            session,
            session.round,
        )
        vote_tally_rows = PlayView._build_vote_tally_rows(
            tally,
            participants,
        )
        vote_rows = PlayView._get_vote_rows(session)
        return {
            "existing_natural_vote": existing_vote,
            "vote_form": game.forms.VoteForm(
                session=session,
                voter=current_participant,
            ),
            "vote_tally": tally,
            "vote_tally_rows": vote_tally_rows,
            "vote_rows": vote_rows,
        }

    @staticmethod
    def _get_existing_vote(session, current_participant):
        query = game.models.VoteRecord.objects.filter(
            session=session,
            round=session.round,
            voter=current_participant,
            kind=game.models.VoteRecord.KIND_NATURAL,
        )
        return query.select_related("target__user").first()

    @staticmethod
    def _build_vote_tally_rows(tally, participants):
        by_id = {participant.pk: participant for participant in participants}
        rows = []
        for participant_id, score in tally:
            username = (
                by_id[participant_id].user.username
                if participant_id in by_id
                else f"#{participant_id}"
            )
            rows.append(
                {
                    "participant_id": participant_id,
                    "username": username,
                    "score": score,
                },
            )

        return rows

    @staticmethod
    def _get_vote_rows(session):
        query = game.models.VoteRecord.objects.filter(
            session=session,
            round=session.round,
        )
        return list(query.select_related("voter__user", "target__user"))

    @staticmethod
    def _get_participant_by_id(participants, participant_id):
        if participant_id is None:
            return None

        by_id = {participant.pk: participant for participant in participants}
        return by_id.get(participant_id)

    @staticmethod
    def _night_selected_target_id_for_role(session_id: str, role_code: str):
        if role_code == game.constants.ROLE_MAFIA:
            return game.redis_store.get_night_kill_target(session_id)

        if role_code == game.constants.ROLE_DOCTOR:
            return game.redis_store.get_night_heal_target(session_id)

        if role_code == game.constants.ROLE_SHERIFF:
            return game.redis_store.get_night_check_target(session_id)

        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request
        scheme = "wss" if request.is_secure() else "ws"
        host = request.get_host()
        session = self.object
        context["ws_url"] = f"{scheme}://{host}/ws/game/{session.pk}/"

        current_participant = session.participants.select_related("user").get(
            user=request.user,
        )
        context["me"] = current_participant
        context["participants"] = list(
            session.participants.select_related("user").order_by(
                "user__username",
            ),
        )

        context["trait_form"] = game.forms.TraitPrepForm(
            initial=current_participant.traits or {}
        )
        context["night_evidences"] = session.evidences.filter(
            round=session.round
        ).exclude(text_ui="")

        session_id = str(session.pk)
        state = game.redis_store.get_game_state(session_id)
        context["last_night_result_known"] = "last_night_killed_id" in state

        killed_participant_id = state.get("last_night_killed_id")
        killed_participant = self._get_participant_by_id(
            context["participants"],
            killed_participant_id,
        )
        context["last_night_killed"] = killed_participant

        selected_target_id = self._night_selected_target_id_for_role(
            session_id,
            current_participant.role,
        )
        selected_target = self._get_participant_by_id(
            context["participants"],
            selected_target_id,
        )
        context["night_selected_target"] = selected_target

        if session.phase == "day_vote":
            context.update(
                self._build_vote_context(
                    session,
                    current_participant,
                    context["participants"],
                ),
            )

        profile, _ = self._get_or_create_profile(request.user)
        context["player_profile"] = profile
        context["max_players"] = session.max_players
        context["hints_payload"] = (
            game.services.hints.build_hint_payload_for_player(
                request.user,
                session,
                current_participant,
            )
        )

        if current_participant.role == game.constants.ROLE_SHERIFF:
            context["sheriff_checks"] = (
                current_participant.sheriff_checks or []
            )

        return context


class PhaseAdvanceView(
    django.contrib.auth.mixins.LoginRequiredMixin,
    django.views.View,
):
    @staticmethod
    def _get_session_or_404(pk):
        return django.shortcuts.get_object_or_404(
            game.models.GameSession,
            pk=pk,
        )

    def post(self, request, pk, *args, **kwargs):
        session = self._get_session_or_404(pk)
        if not session.participants.filter(user=request.user).exists():
            raise django.core.exceptions.PermissionDenied()

        seq_param = request.POST.get("client_seq")
        client_seq = int(seq_param) if seq_param else None
        ok, payload = game.fsm.transition(
            str(session.pk),
            "advance",
            client_seq=client_seq,
        )
        if ok:
            django.contrib.messages.success(
                request,
                "Переход к следующей фазе выполнен.",
            )
        else:
            django.contrib.messages.error(
                request,
                game.fsm.transition_error_user_message(payload),
            )

        return django.shortcuts.redirect("game:play", pk=pk)


class GameStateView(
    django.contrib.auth.mixins.LoginRequiredMixin,
    django.views.View,
):
    @staticmethod
    def _get_session_or_404(pk):
        return django.shortcuts.get_object_or_404(
            game.models.GameSession,
            pk=pk,
        )

    def get(self, request, pk, *args, **kwargs):
        session = self._get_session_or_404(pk)
        current_participant = session.participants.filter(
            user=request.user
        ).first()
        if current_participant is None:
            raise django.core.exceptions.PermissionDenied()

        payload = {
            "seq": session.seq,
            "phase": session.phase,
            "round": session.round,
            "ends_at": (
                session.ends_at.isoformat() if session.ends_at else None
            ),
        }
        if session.win_summary:
            payload["win_summary"] = session.win_summary

        payload.update(
            game.services.hints.build_hint_payload_for_player(
                request.user,
                session,
                current_participant,
            ),
        )
        return django.http.JsonResponse(payload)


class VoteSubmitView(
    django.contrib.auth.mixins.LoginRequiredMixin,
    django.views.View,
):
    @staticmethod
    def _redirect_to_play(pk):
        return django.shortcuts.redirect("game:play", pk=pk)

    @staticmethod
    def _get_session_or_404(pk):
        return django.shortcuts.get_object_or_404(
            game.models.GameSession,
            pk=pk,
        )

    @staticmethod
    def _reject_vote_phase(request, pk):
        django.contrib.messages.error(
            request,
            "Сейчас голосование недоступно.",
        )
        return django.shortcuts.redirect("game:play", pk=pk)

    @staticmethod
    def _reject_dead_voter(request, pk):
        django.contrib.messages.error(
            request,
            "Вы выбыли из партии и больше не можете голосовать.",
        )
        return django.shortcuts.redirect("game:play", pk=pk)

    @staticmethod
    def _reject_duplicate_vote(request, pk):
        django.contrib.messages.info(
            request,
            "Ваш голос в этом раунде уже принят. Переголосование недоступно.",
        )
        return django.shortcuts.redirect("game:play", pk=pk)

    @staticmethod
    def _reject_invalid_form(request, pk):
        django.contrib.messages.error(
            request,
            "Не удалось принять голос. Проверьте выбор и попробуйте снова.",
        )
        return django.shortcuts.redirect("game:play", pk=pk)

    def post(self, request, pk, *args, **kwargs):
        session = self._get_session_or_404(pk)
        if not session.participants.filter(user=request.user).exists():
            raise django.core.exceptions.PermissionDenied()

        if session.phase != "day_vote":
            return self._reject_vote_phase(request, pk)

        voter = session.participants.get(user=request.user)
        if not voter.is_alive:
            return self._reject_dead_voter(request, pk)

        existing_vote = game.models.VoteRecord.objects.filter(
            session=session,
            round=session.round,
            voter=voter,
            kind=game.models.VoteRecord.KIND_NATURAL,
        ).first()
        if existing_vote is not None:
            return self._reject_duplicate_vote(request, pk)

        form = game.forms.VoteForm(
            request.POST,
            session=session,
            voter=voter,
        )
        if not form.is_valid():
            return self._reject_invalid_form(request, pk)

        target = form.cleaned_data["target"]
        game.models.VoteRecord.objects.create(
            session=session,
            round=session.round,
            voter=voter,
            kind=game.models.VoteRecord.KIND_NATURAL,
            target=target,
            artifact_key="",
        )
        game.broadcasting.send_to_room_group(
            str(session.pk),
            "votes.updated",
            {"round": session.round},
        )
        django.contrib.messages.success(request, "Голос принят.")
        return self._redirect_to_play(pk)


class NightActionSubmitView(
    django.contrib.auth.mixins.LoginRequiredMixin,
    django.views.View,
):
    @staticmethod
    def _redirect_to_play(pk):
        return django.shortcuts.redirect("game:play", pk=pk)

    @staticmethod
    def _get_session_or_404(pk):
        return django.shortcuts.get_object_or_404(
            game.models.GameSession,
            pk=pk,
        )

    @staticmethod
    def _parse_night_payload(request):
        kind = (request.POST.get("kind") or "").strip()
        target_id = (request.POST.get("target_id") or "").strip()
        return kind, target_id

    @staticmethod
    def _reject_night_phase(request, pk):
        django.contrib.messages.error(
            request,
            "Ночные действия сейчас недоступны.",
        )
        return django.shortcuts.redirect("game:play", pk=pk)

    @staticmethod
    def _reject_night_payload(request, pk):
        django.contrib.messages.error(
            request,
            "Выберите цель и попробуйте снова.",
        )
        return django.shortcuts.redirect("game:play", pk=pk)

    @staticmethod
    def _reject_night_failure(request, pk):
        django.contrib.messages.error(
            request,
            "Не удалось принять ночное действие.",
        )
        return django.shortcuts.redirect("game:play", pk=pk)

    @staticmethod
    def _reject_night_service_error(request, pk, payload):
        django.contrib.messages.error(
            request,
            payload.get("message") or "Не удалось принять ночное действие.",
        )
        return django.shortcuts.redirect("game:play", pk=pk)

    def post(self, request, pk, *args, **kwargs):
        session = self._get_session_or_404(pk)
        if not session.participants.filter(user=request.user).exists():
            raise django.core.exceptions.PermissionDenied()

        if session.phase != game.constants.PHASE_NIGHT:
            return self._reject_night_phase(request, pk)

        kind, target_id = self._parse_night_payload(request)
        if not kind or not target_id:
            return self._reject_night_payload(request, pk)

        try:
            ok, payload = game.services.night_ws.set_night_action_from_ws(
                str(session.pk),
                request.user.pk,
                kind,
                target_id,
            )
        except (
            game.models.Participant.DoesNotExist,
            game.models.GameSession.DoesNotExist,
            ValueError,
            django.core.exceptions.ValidationError,
        ):
            return self._reject_night_failure(request, pk)

        if not ok:
            return self._reject_night_service_error(
                request,
                pk,
                payload,
            )

        django.contrib.messages.success(
            request,
            "Ночное действие зафиксировано.",
        )
        return self._redirect_to_play(pk)


class PlayerSettingsView(
    django.contrib.auth.mixins.LoginRequiredMixin,
    django.views.View,
):
    def post(self, request, *args, **kwargs):
        profile, _ = game.models.PlayerProfile.objects.get_or_create(
            user=request.user,
            defaults=PROFILE_DEFAULTS,
        )
        hints = request.POST.get("hints_enabled")
        profile.hints_enabled = hints in ("1", "on", "true", "yes")
        lang = (request.POST.get("preferred_language") or "ru").lower()
        profile.preferred_language = lang if lang in ("ru", "en") else "ru"
        profile.save(update_fields=["hints_enabled", "preferred_language"])
        django.contrib.messages.success(request, "Настройки сохранены.")
        ref = request.META.get("HTTP_REFERER")
        if ref:
            return django.shortcuts.redirect(ref)

        return django.shortcuts.redirect("lobby:lobby_list")


class ParticipantTraitsView(
    django.contrib.auth.mixins.LoginRequiredMixin, django.views.View
):
    def post(self, request, pk):
        session = django.shortcuts.get_object_or_404(
            game.models.GameSession, pk=pk
        )
        participant = session.participants.get(user=request.user)

        form = game.forms.TraitPrepForm(request.POST)
        if form.is_valid():
            participant.traits = form.cleaned_data
            participant.save(update_fields=["traits"])

            django.contrib.messages.success(
                request, "Ваш образ успешно сохранен."
            )
            return django.shortcuts.redirect("game:play", pk=pk)

        django.contrib.messages.error(request, "Ошибка при заполнении примет.")
        return django.shortcuts.redirect("game:play", pk=pk)
