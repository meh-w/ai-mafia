__all__ = (
    "MAFIA_ROLES",
    "TOWN_ROLES",
    "check_win_conditions",
    "maybe_finish_after_vote",
    "maybe_finish_after_night",
    "finalize_if_won",
)

from typing import Any, Dict, Optional

import game.constants
import game.models

MAFIA_ROLES = frozenset(game.constants.MAFIA_ROLE_CODES)
TOWN_ROLES = frozenset(game.constants.TOWN_ROLE_CODES)


def _summary(
    primary: str,
    reason_code: str,
    reason: str,
) -> Dict[str, Any]:
    return {
        "primary": primary,
        "reason_code": reason_code,
        "reason": reason,
    }


def _alive_counts(session: game.models.GameSession) -> tuple[int, int]:
    parts = list(session.participants.all())
    mafia_alive = sum(
        1 for part in parts if part.is_alive and part.role in MAFIA_ROLES
    )
    town_alive = sum(
        1 for part in parts if part.is_alive and part.role not in MAFIA_ROLES
    )
    return mafia_alive, town_alive


def _elimination_summary(mafia_alive: int) -> Dict[str, Any]:
    if mafia_alive > 0:
        return _summary(
            "mafia",
            "elimination",
            "Мирные полностью выбыли из игры.",
        )

    return _summary(
        "draw",
        "elimination",
        "Все стороны выбыли одновременно.",
    )


def check_win_conditions(
    session: game.models.GameSession,
) -> Optional[Dict[str, Any]]:
    mafia_alive, town_alive = _alive_counts(session)

    if mafia_alive == 0 and town_alive > 0:
        return _summary(
            "town",
            "elimination",
            "Вся мафия устранена.",
        )

    if town_alive == 0:
        return _elimination_summary(mafia_alive)

    if mafia_alive >= town_alive:
        return _summary(
            "mafia",
            "parity",
            "Мафия достигла паритета или перевеса над мирными.",
        )

    return None


def _finalize_session(
    session: game.models.GameSession,
    summary: Dict[str, Any],
) -> None:
    session.phase = game.constants.PHASE_FINISHED
    session.status = "finished"
    session.ends_at = None
    session.win_summary = summary
    session.seq = session.seq + 1
    session.save(
        update_fields=[
            "phase",
            "status",
            "ends_at",
            "win_summary",
            "seq",
            "updated_at",
        ],
    )


def _push_session_state_to_redis_and_broadcast(
    session: game.models.GameSession,
) -> None:
    import game.redis_store

    sid = str(session.pk)
    state: Dict[str, Any] = {
        "phase": session.phase,
        "round": session.round,
        "seq": session.seq,
        "ends_at": (session.ends_at.isoformat() if session.ends_at else None),
    }
    if session.win_summary:
        state["win_summary"] = session.win_summary

    game.redis_store.set_game_state(sid, state)
    _broadcast_win(sid, session)


def finalize_if_won(
    session: game.models.GameSession,
) -> Optional[Dict[str, Any]]:
    session.refresh_from_db()
    summary = check_win_conditions(session)
    if not summary:
        return None

    _finalize_session(session, summary)
    _push_session_state_to_redis_and_broadcast(session)
    return summary


def maybe_finish_after_vote(
    session: game.models.GameSession,
) -> Optional[Dict[str, Any]]:
    return finalize_if_won(session)


def maybe_finish_after_night(
    session: game.models.GameSession,
) -> Optional[Dict[str, Any]]:
    return finalize_if_won(session)


def _broadcast_win(session_id: str, session: game.models.GameSession) -> None:
    import game.broadcasting

    payload = {
        "phase": session.phase,
        "round": session.round,
        "seq": session.seq,
        "ends_at": None,
        "win_summary": session.win_summary,
    }
    game.broadcasting.send_to_room_group(
        session_id,
        "phase.changed",
        payload,
    )
