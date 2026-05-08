__all__ = ("append_public_chat_message",)

from typing import Any, Dict, Tuple
import uuid

import django.utils.timezone

import game.constants
import game.models
import game.redis_store


def append_public_chat_message(
    session_id: str,
    user_id: int,
    text: str,
) -> Tuple[bool, Dict[str, Any]]:
    try:
        session = game.models.GameSession.objects.get(pk=session_id)
    except game.models.GameSession.DoesNotExist:
        return False, {"code": "not_found"}

    if session.phase != game.constants.PHASE_DAY_DISCUSSION:
        return False, {"code": "wrong_phase"}

    balance_config = session.balance_config or {}
    messages_per_minute_limit = int(
        balance_config.get("rate_limit", {}).get("messages_per_minute", 30)
    )
    if not game.redis_store.rate_limit_allow(
        user_id,
        session_id,
        messages_per_minute_limit,
    ):
        return False, {"code": "rate_limited"}

    participant = game.models.Participant.objects.get(
        session=session,
        user_id=user_id,
    )
    if not participant.is_alive:
        return False, {"code": "forbidden"}

    payload = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "username": participant.user.username,
        "text": text[:2000],
        "ts": django.utils.timezone.now().isoformat(),
    }
    game.redis_store.push_chat_message(session_id, payload)

    _broadcast_chat(session_id, payload)

    return True, {"broadcast": payload}


def _broadcast_chat(session_id: str, payload: Dict[str, Any]) -> None:
    import game.broadcasting

    game.broadcasting.send_to_room_group(
        session_id,
        "chat.message",
        payload,
    )
