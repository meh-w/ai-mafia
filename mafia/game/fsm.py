__all__ = (
    "FSMError",
    "transition",
    "transition_by_deadline",
    "transition_error_user_message",
)

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any, Dict, Optional, Tuple

from django.conf import settings
from django.db import transaction
import django.utils.timezone

from game.constants import (
    DEFAULT_PHASE_SECONDS,
    PHASE_DAY_DISCUSSION,
    PHASE_DAY_VOTE,
    PHASE_FINISHED,
    PHASE_LOBBY,
    PHASE_NIGHT,
    PHASE_PREPARATION,
)
import game.models
import game.redis_store
import game.services.classic_night
import game.services.roles
import game.services.voting
import game.services.win_conditions

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FSMError:
    code: str
    message: str


def _duration_for_phase(
    balance_config: Dict[str, Any],
    phase: str,
) -> int:
    seconds = balance_config.get("phase_seconds", {}).get(
        phase,
        balance_config.get("default_phase_seconds", DEFAULT_PHASE_SECONDS),
    )
    return int(seconds)


def _apply_scheduling_for_new_phase(
    session: game.models.GameSession,
    new_phase: str,
) -> None:
    if new_phase == PHASE_FINISHED:
        session.status = "finished"
        session.ends_at = None
        return

    if settings.DEBUG:
        session.ends_at = None
        return

    seconds = _duration_for_phase(
        session.balance_config or {},
        new_phase,
    )
    session.ends_at = django.utils.timezone.now() + timedelta(seconds=seconds)


def _validate_lobby_start(
    session: game.models.GameSession,
) -> Optional[Tuple[bool, Dict[str, Any]]]:
    participants_count = session.participants.count()
    required_players_count = session.max_players

    if participants_count != required_players_count:
        return False, {
            "error": {
                "code": "lobby_not_full",
                "details": {
                    "have": participants_count,
                    "need": required_players_count,
                },
            },
        }

    return None


def _build_state_payload(
    session: game.models.GameSession,
    night_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload = {
        "phase": session.phase,
        "round": session.round,
        "seq": session.seq,
        "ends_at": (session.ends_at.isoformat() if session.ends_at else None),
        **(
            {"win_summary": session.win_summary} if session.win_summary else {}
        ),
    }
    if night_result is not None:
        payload["last_night_killed_id"] = night_result.get("killed")

    return payload


def _save_state_to_redis(
    session_id: str,
    state_payload: Dict[str, Any],
) -> None:
    payload = {
        "phase": state_payload["phase"],
        "round": state_payload["round"],
        "seq": state_payload["seq"],
        "ends_at": state_payload.get("ends_at"),
    }
    if state_payload.get("win_summary"):
        payload["win_summary"] = state_payload["win_summary"]

    previous_state = game.redis_store.get_game_state(session_id)
    if "last_night_killed_id" in state_payload:
        payload["last_night_killed_id"] = state_payload["last_night_killed_id"]
    elif "last_night_killed_id" in previous_state:
        payload["last_night_killed_id"] = previous_state[
            "last_night_killed_id"
        ]

    game.redis_store.set_game_state(session_id, payload)


def _reject_stale_seq(
    client_seq: Optional[int],
    session: game.models.GameSession,
) -> Optional[Tuple[bool, Dict[str, Any]]]:
    if client_seq is None or client_seq >= session.seq:
        return None

    return False, {
        "error": {
            "code": "stale_state",
            "message": "Устаревший seq",
            "current_seq": session.seq,
        },
    }


def _reject_invalid_event(
    event: str,
    session: game.models.GameSession,
) -> Optional[Tuple[bool, Dict[str, Any]]]:
    if event == "advance":
        return None

    return False, {
        "error": {
            "code": "invalid_transition",
            "message": f"{session.phase!r} + {event!r}",
        },
    }


def _reject_finished_phase(
    session: game.models.GameSession,
) -> Optional[Tuple[bool, Dict[str, Any]]]:
    if session.phase != PHASE_FINISHED:
        return None

    return False, {
        "error": {
            "code": "invalid_transition",
            "message": "finished",
        },
    }


def _finalize_if_won(
    session: game.models.GameSession,
    session_id: str,
) -> Optional[Tuple[bool, Dict[str, Any]]]:
    summary = game.services.win_conditions.finalize_if_won(session)
    if not summary:
        return None

    state_payload = _build_state_payload(session)
    _save_state_to_redis(session_id, state_payload)
    _broadcast(session_id, state_payload)
    return True, {"state": state_payload}


def _advance_from_lobby(
    session: game.models.GameSession,
) -> Optional[Tuple[bool, Dict[str, Any]]]:
    validation_error = _validate_lobby_start(session)
    if validation_error is not None:
        return validation_error

    game.services.roles.assign_roles(session)
    session.status = "active"
    session.phase = PHASE_NIGHT
    session.round = 0
    session.seq = session.seq + 1
    _apply_scheduling_for_new_phase(session, session.phase)
    session.save()
    return None


def _advance_from_day_discussion(
    session: game.models.GameSession,
) -> None:
    session.phase = PHASE_DAY_VOTE
    session.seq = session.seq + 1
    _apply_scheduling_for_new_phase(session, session.phase)
    session.save()


def _advance_from_day_vote(
    session: game.models.GameSession,
    session_id: str,
    pre_round: int,
) -> Optional[Tuple[bool, Dict[str, Any]]]:
    game.services.voting.apply_day_vote_exclusion(session, pre_round)
    finished = _finalize_if_won(session, session_id)
    if finished is not None:
        return finished

    session.participants.all().update(last_night_result=None)

    session.phase = PHASE_NIGHT
    session.seq = session.seq + 1
    _apply_scheduling_for_new_phase(session, session.phase)
    session.save()
    return None


def _advance_from_night(
    session: game.models.GameSession,
    session_id: str,
    pre_round: int,
) -> Optional[Tuple[bool, Dict[str, Any]]]:
    night_result = game.services.classic_night.resolve_classic_night(
        session,
        pre_round,
    )
    finished = _finalize_if_won(session, session_id)
    if finished is not None:
        return finished

    session.phase = PHASE_DAY_DISCUSSION
    session.round = pre_round + 1
    session.seq = session.seq + 1
    _apply_scheduling_for_new_phase(session, session.phase)
    session.save()
    return True, {"night_result": night_result}


def _advance_session(
    session: game.models.GameSession,
    session_id: str,
    pre_round: int,
) -> Optional[Tuple[bool, Dict[str, Any]]]:
    if session.phase == PHASE_LOBBY:
        return _advance_from_lobby(session)

    if session.phase == PHASE_DAY_DISCUSSION:
        _advance_from_day_discussion(session)
        return None

    if session.phase == PHASE_DAY_VOTE:
        return _advance_from_day_vote(session, session_id, pre_round)

    if session.phase == PHASE_NIGHT:
        return _advance_from_night(session, session_id, pre_round)

    return False, {
        "error": {
            "code": "invalid_transition",
            "message": session.phase,
        },
    }


def _get_next_phase_state(phase: str, round_num: int) -> tuple[str, int]:
    mapping = {
        PHASE_LOBBY: (PHASE_PREPARATION, 1),
        PHASE_PREPARATION: (PHASE_NIGHT, round_num),
        PHASE_NIGHT: (PHASE_DAY_DISCUSSION, round_num),
        PHASE_DAY_DISCUSSION: (PHASE_DAY_VOTE, round_num),
        PHASE_DAY_VOTE: (PHASE_NIGHT, round_num + 1),
    }
    return mapping.get(phase, (phase, round_num))


def _run_transition_locked(
    session: game.models.GameSession,
    session_id: str,
    event: str,
    client_seq: Optional[int],
) -> Tuple[bool, Dict[str, Any]]:
    if client_seq is not None and client_seq < session.seq:
        return False, {
            "error": {"code": "out_of_sync", "message": "Синхронизация..."}
        }

    if event == "advance":
        if session.phase == PHASE_LOBBY:
            session.status = "active"
            game.services.roles.assign_roles_classic(session)
        elif session.phase == PHASE_NIGHT:
            game.services.classic_night.resolve_classic_night(
                session, session.round
            )

        session.phase, session.round = _get_next_phase_state(
            session.phase, session.round
        )

    win_data = game.services.win_conditions.check_win_conditions(session)
    if win_data:
        session.phase = PHASE_FINISHED
        session.win_summary = win_data

    session.seq += 1
    _apply_scheduling_for_new_phase(session, session.phase)
    session.save()

    return True, {
        "state": {
            "phase": session.phase,
            "round": session.round,
            "seq": session.seq,
            "ends_at": (
                session.ends_at.isoformat() if session.ends_at else None
            ),
            "win_summary": session.win_summary,
        }
    }


def transition(
    session_id: str,
    event: str,
    client_seq: Optional[int] = None,
) -> Tuple[bool, Dict[str, Any]]:
    lock_id = game.redis_store.acquire_game_lock(session_id)
    if not lock_id:
        return False, {"error": {"code": "lock_busy", "message": "Занято"}}
    try:
        with transaction.atomic():
            session = game.models.GameSession.objects.select_for_update().get(
                pk=session_id
            )
            ok, payload = _run_transition_locked(
                session, session_id, event, client_seq
            )
        if not ok:
            return False, payload
        _broadcast(session_id, payload["state"])
        return True, payload
    finally:
        game.redis_store.release_game_lock(session_id, lock_id)


def _msg_lobby_not_full(err: Dict[str, Any]) -> str:
    details = err.get("details") or {}
    have = details.get("have")
    need = details.get("need")
    return (
        f"Нельзя начать игру: за столом {have} из {need} игроков. "
        "Дождитесь полного стола."
    )


def transition_error_user_message(payload: Dict[str, Any]) -> str:
    fallback = (
        "Сервер временно не может выполнить действие. " "Попробуйте ещё раз."
    )
    error_payload = payload.get("error")
    if not isinstance(error_payload, dict):
        return fallback

    handlers = {
        "lobby_not_full": _msg_lobby_not_full,
        "stale_state": (
            lambda _err: (
                "Страница устарела относительно сервера. Обновите её (F5) "
                "и при необходимости нажмите кнопку ещё раз."
            )
        ),
        "lock_busy": (
            lambda _err: (
                "Сервер обрабатывает другой переход. Попробуйте через секунду."
            )
        ),
        "invalid_transition": (
            lambda _err: (
                "Сейчас этот переход невозможен в текущей фазе игры."
            )
        ),
    }
    code = error_payload.get("code")
    handler = handlers.get(code)
    if handler is None:
        return fallback

    return handler(error_payload)


def transition_by_deadline(session_id: str) -> Optional[FSMError]:
    session = game.models.GameSession.objects.filter(pk=session_id).first()
    if session is None or session.ends_at is None:
        return None

    if session.ends_at > django.utils.timezone.now():
        return None

    try:
        ok, payload = transition(session_id, "advance")
    except Exception as exc:
        logger.exception(
            "Deadline transition failed with exception",
            extra={"session_id": session_id},
        )
        return FSMError(exc.__class__.__name__.lower(), str(exc))

    if ok:
        return None

    error = payload.get("error", {})
    logger.warning(
        "Deadline transition rejected",
        extra={
            "session_id": session_id,
            "code": str(error.get("code", "fsm")),
            "error_message": str(error.get("message", "")),
        },
    )
    return FSMError(
        str(error.get("code", "fsm")),
        str(error.get("message", "")),
    )


def _broadcast(session_id: str, state_payload: Dict[str, Any]) -> None:
    import game.broadcasting

    broadcast_payload = {
        "phase": state_payload["phase"],
        "round": state_payload["round"],
        "seq": state_payload["seq"],
        "ends_at": state_payload["ends_at"],
    }
    if state_payload.get("win_summary"):
        broadcast_payload["win_summary"] = state_payload["win_summary"]

    game.broadcasting.send_to_room_group(
        session_id,
        "phase.changed",
        broadcast_payload,
    )
