__all__ = ("build_hint_payload_for_player",)

from typing import Any, Dict, Tuple

import django.contrib.auth.models
import django.utils.translation
from django.utils.translation import gettext

import game.constants
import game.models


def _hint_msgids(phase: str, role_code: str) -> Tuple[str, str]:
    resolved_role_code = role_code or game.constants.ROLE_CIVILIAN
    if phase == game.constants.PHASE_LOBBY:
        return ("hint_title_lobby", "hint_body_lobby")

    if phase == game.constants.PHASE_DAY_VOTE:
        return ("hint_title_vote", "hint_body_vote")

    if phase == game.constants.PHASE_FINISHED:
        return ("hint_title_finished", "hint_body_finished")

    if phase == game.constants.PHASE_DAY_DISCUSSION:
        day_map = {
            game.constants.ROLE_MAFIA: (
                "hint_title_day_mafia",
                "hint_body_day_discussion_mafia",
            ),
            game.constants.ROLE_SHERIFF: (
                "hint_title_day_sheriff",
                "hint_body_day_discussion_sheriff",
            ),
            game.constants.ROLE_DOCTOR: (
                "hint_title_day_doctor",
                "hint_body_day_discussion_doctor",
            ),
        }
        return day_map.get(
            resolved_role_code,
            ("hint_title_day_civilian", "hint_body_day_discussion_civilian"),
        )

    if phase == game.constants.PHASE_NIGHT:
        night_map = {
            game.constants.ROLE_MAFIA: (
                "hint_title_night_mafia",
                "hint_body_night_mafia",
            ),
            game.constants.ROLE_SHERIFF: (
                "hint_title_night_sheriff",
                "hint_body_night_sheriff",
            ),
            game.constants.ROLE_DOCTOR: (
                "hint_title_night_doctor",
                "hint_body_night_doctor",
            ),
        }
        return night_map.get(
            resolved_role_code,
            ("hint_title_night_civilian", "hint_body_night_civilian"),
        )

    return ("", "")


def build_hint_payload_for_player(
    user: django.contrib.auth.models.AbstractUser,
    session: game.models.GameSession,
    participant: game.models.Participant,
) -> Dict[str, Any]:
    profile, _ = game.models.PlayerProfile.objects.get_or_create(
        user=user,
        defaults={
            "hints_enabled": True,
            "preferred_language": "ru",
        },
    )
    if not profile.hints_enabled:
        return {}

    lang = (
        profile.preferred_language
        if profile.preferred_language in ("ru", "en")
        else "ru"
    )
    title_msgid, body_msgid = _hint_msgids(session.phase, participant.role)
    with django.utils.translation.override(lang):
        title = gettext(title_msgid) if title_msgid else ""
        body = gettext(body_msgid) if body_msgid else ""

    return {
        "hint_title": title,
        "hint_body": body,
        "hint_locale": lang,
    }
