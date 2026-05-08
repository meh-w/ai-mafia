__all__ = (
    "set_kill_target_from_ws",
    "set_heal_target_from_ws",
    "set_check_target_from_ws",
    "set_night_action_from_ws",
)

from typing import Any, Dict, Tuple

import game.constants
import game.models
import game.redis_store
from game.services.win_conditions import MAFIA_ROLES


def _err(code: str, message: str) -> Tuple[bool, Dict[str, Any]]:
    return False, {"code": code, "message": message}


def set_kill_target_from_ws(
    session_id: str,
    user_id: int,
    target_id: str,
) -> Tuple[bool, Dict[str, Any]]:
    session = game.models.GameSession.objects.get(pk=session_id)
    if session.phase != game.constants.PHASE_NIGHT:
        return _err("wrong_phase", "Ночное действие сейчас недоступно.")
    acting_participant = game.models.Participant.objects.get(
        session=session,
        user_id=user_id,
    )
    if (
        acting_participant.role not in MAFIA_ROLES
        or not acting_participant.is_alive
    ):
        return _err("forbidden", "Это действие недоступно для вашей роли.")
    target_participant = game.models.Participant.objects.get(
        pk=target_id,
        session=session,
    )
    if (
        not target_participant.is_alive
        or target_participant.role in MAFIA_ROLES
    ):
        return _err("bad_target", "Эту цель выбрать нельзя.")
    game.redis_store.set_night_kill_target(
        session_id,
        int(target_participant.pk),
    )
    return True, {}


def set_heal_target_from_ws(
    session_id: str,
    user_id: int,
    target_id: str,
) -> Tuple[bool, Dict[str, Any]]:
    session = game.models.GameSession.objects.get(pk=session_id)
    if session.phase != game.constants.PHASE_NIGHT:
        return _err("wrong_phase", "Ночное действие сейчас недоступно.")
    acting_participant = game.models.Participant.objects.get(
        session=session,
        user_id=user_id,
    )
    if (
        acting_participant.role != game.constants.ROLE_DOCTOR
        or not acting_participant.is_alive
    ):
        return _err("forbidden", "Это действие недоступно для вашей роли.")
    target_participant = game.models.Participant.objects.get(
        pk=target_id,
        session=session,
    )
    if not target_participant.is_alive:
        return _err("bad_target", "Эту цель выбрать нельзя.")
    last_healed_participant = session.doctor_last_healed
    if last_healed_participant is not None and int(
        last_healed_participant.pk
    ) == int(target_participant.pk):
        return _err(
            "doctor_same_target_twice",
            "Доктор не может лечить одного и того же игрока две ночи подряд.",
        )
    game.redis_store.set_night_heal_target(
        session_id,
        int(target_participant.pk),
    )
    return True, {}


def set_check_target_from_ws(
    session_id: str,
    user_id: int,
    target_id: str,
) -> Tuple[bool, Dict[str, Any]]:
    session = game.models.GameSession.objects.get(pk=session_id)
    if session.phase != game.constants.PHASE_NIGHT:
        return _err("wrong_phase", "Ночное действие сейчас недоступно.")
    acting_participant = game.models.Participant.objects.get(
        session=session,
        user_id=user_id,
    )
    if (
        acting_participant.role != game.constants.ROLE_SHERIFF
        or not acting_participant.is_alive
    ):
        return _err("forbidden", "Это действие недоступно для вашей роли.")
    target_participant = game.models.Participant.objects.get(
        pk=target_id,
        session=session,
    )
    if not target_participant.is_alive:
        return _err("bad_target", "Эту цель выбрать нельзя.")
    if int(target_participant.pk) == int(acting_participant.pk):
        return _err("bad_target", "Эту цель выбрать нельзя.")
    game.redis_store.set_night_check_target(
        session_id,
        int(target_participant.pk),
    )
    return True, {}


def set_night_action_from_ws(
    session_id: str,
    user_id: int,
    kind: str,
    target_id: str,
) -> Tuple[bool, Dict[str, Any]]:
    if kind == "kill":
        return set_kill_target_from_ws(session_id, user_id, target_id)
    if kind == "heal":
        return set_heal_target_from_ws(session_id, user_id, target_id)
    if kind == "check":
        return set_check_target_from_ws(session_id, user_id, target_id)
    return _err("unknown_kind", "Неизвестный тип ночного действия.")
