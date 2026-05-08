__all__ = (
    "LobbyListView",
    "SessionCreateView",
    "SessionJoinView",
)


import secrets

import django.contrib.auth.mixins
import django.contrib.messages
import django.shortcuts
import django.urls
import django.views.generic

import game.balance
import game.broadcasting
import game.constants
import game.models
import lobby.forms


class LobbyListView(
    django.contrib.auth.mixins.LoginRequiredMixin,
    django.views.generic.ListView,
):
    template_name = "lobby/list.html"
    context_object_name = "sessions"

    def get_queryset(self):
        return game.models.GameSession.objects.exclude(
            status="finished"
        ).order_by("-created_at")[:50]

    @staticmethod
    def _joined_room_card(session, players_count):
        return {
            "session": session,
            "players_count": players_count,
            "state_text": "Вы уже в этой комнате",
            "cta_href": django.urls.reverse(
                "game:play",
                kwargs={"pk": session.pk},
            ),
            "cta_label": "Открыть комнату",
            "cta_disabled": False,
        }

    @staticmethod
    def _join_by_code_card(session, players_count):
        return {
            "session": session,
            "players_count": players_count,
            "state_text": "Ожидание игроков, вход по коду",
            "cta_href": (
                f"{django.urls.reverse('lobby:join')}?code={session.slug}"
            ),
            "cta_label": "Ввести код",
            "cta_disabled": False,
        }

    @staticmethod
    def _disabled_room_card(session, players_count):
        if players_count >= session.max_players:
            state_text = "Комната заполнена"
        elif session.status == "finished":
            state_text = "Игра завершена"
        else:
            state_text = "Игра уже началась"

        return {
            "session": session,
            "players_count": players_count,
            "state_text": state_text,
            "cta_href": "",
            "cta_label": "Недоступно",
            "cta_disabled": True,
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        cards = []
        for session in context["sessions"]:
            players_count = session.participants.count()
            user_in_session = session.participants.filter(user=user).exists()
            is_lobby_phase = session.phase == game.constants.PHASE_LOBBY
            has_free_slots = players_count < session.max_players
            can_join_by_code = (
                session.status == "lobby" and is_lobby_phase and has_free_slots
            )

            if user_in_session:
                cards.append(self._joined_room_card(session, players_count))
                continue

            if can_join_by_code:
                cards.append(self._join_by_code_card(session, players_count))
                continue

            cards.append(self._disabled_room_card(session, players_count))

        context["room_cards"] = cards
        return context


class SessionCreateView(
    django.contrib.auth.mixins.LoginRequiredMixin,
    django.views.generic.FormView,
):
    template_name = "lobby/create.html"
    form_class = lobby.forms.SessionCreateForm

    def form_valid(self, form):
        slug = secrets.token_hex(4)
        max_players = form.cleaned_data["max_players"]
        session = game.models.GameSession.objects.create(
            slug=slug,
            status="lobby",
            phase=game.constants.PHASE_LOBBY,
            balance_config=game.balance.load_default_balance_config(),
            max_players=max_players,
        )
        game.models.Participant.objects.create(
            session=session,
            user=self.request.user,
        )
        return django.shortcuts.redirect(
            "game:play",
            pk=session.pk,
        )


class SessionJoinView(
    django.contrib.auth.mixins.LoginRequiredMixin,
    django.views.generic.FormView,
):
    template_name = "lobby/join.html"
    form_class = lobby.forms.SessionJoinForm

    def get_initial(self):
        initial = super().get_initial()
        code = (self.request.GET.get("code") or "").strip()
        if code:
            initial["code"] = code

        return initial

    def form_valid(self, form):
        code = form.cleaned_data["code"].strip()
        session = game.models.GameSession.objects.filter(
            slug__iexact=code,
            status="lobby",
        ).first()
        if session is None:
            form.add_error(
                "code",
                "Комната не найдена или уже недоступна.",
            )
            return self.form_invalid(form)

        count = session.participants.count()
        if count >= session.max_players:
            django.contrib.messages.error(
                self.request,
                f"Комната заполнена (лимит {session.max_players} игроков).",
            )
            return django.shortcuts.redirect("lobby:join")

        participant, created = game.models.Participant.objects.get_or_create(
            session=session,
            user=self.request.user,
        )
        if not created:
            django.contrib.messages.info(
                self.request,
                "Вы уже в этой комнате.",
            )
        elif session.phase == game.constants.PHASE_LOBBY:
            participants = list(
                session.participants.select_related("user").order_by(
                    "user__username",
                ),
            )
            game.broadcasting.send_to_room_group(
                str(session.pk),
                "lobby.roster",
                {
                    "players": [
                        {
                            "user_id": p.user_id,
                            "username": p.user.username,
                        }
                        for p in participants
                    ],
                    "count": len(participants),
                    "max_players": session.max_players,
                },
            )

        return django.shortcuts.redirect("game:play", pk=session.pk)
