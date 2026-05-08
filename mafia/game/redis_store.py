__all__ = (
    "acquire_game_lock",
    "release_game_lock",
    "get_game_state",
    "set_game_state",
    "update_game_state",
    "redis_available",
    "push_chat_message",
    "fetch_chat_buffer",
    "trim_chat_buffer",
    "rate_limit_allow",
    "set_night_kill_target",
    "get_night_kill_target",
    "get_and_clear_night_kill_target",
    "set_night_heal_target",
    "get_night_heal_target",
    "get_and_clear_night_heal_target",
    "set_night_check_target",
    "get_night_check_target",
    "get_and_clear_night_check_target",
)

import json
from typing import Any, Dict, Optional
import uuid

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
import redis

LOCK_TTL_SEC = 10
STATE_TTL_SEC = 600
CHAT_BUFFER_MAX = 4000
RATE_WINDOW_SEC = 60

redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def redis_available() -> bool:
    try:
        return redis_client.ping()
    except redis.ConnectionError:
        return False


def acquire_game_lock(
    session_id: str,
    timeout_sec: int = LOCK_TTL_SEC,
) -> Optional[str]:
    if not settings.DEBUG and not redis_available():
        raise ImproperlyConfigured("Redis is not available in production")

    lock_key = f"game:{session_id}:lock"
    lock_id = str(uuid.uuid4())
    success = redis_client.set(lock_key, lock_id, nx=True, ex=timeout_sec)
    return lock_id if success else None


def release_game_lock(session_id: str, lock_id: str) -> bool:
    lock_key = f"game:{session_id}:lock"
    current_lock = redis_client.get(lock_key)

    if current_lock == lock_id:
        redis_client.delete(lock_key)
        return True

    return False


def get_game_state(session_id: str) -> Dict[str, Any]:
    key = f"game:{session_id}:state"
    data = redis_client.get(key)

    if data:
        return json.loads(data)

    return {"phase": "lobby", "round": 0, "seq": 0, "ends_at": None}


def set_game_state(session_id: str, state: Dict[str, Any]) -> None:
    key = f"game:{session_id}:state"
    redis_client.set(key, json.dumps(state), ex=STATE_TTL_SEC)


def update_game_state(session_id: str, **kwargs) -> Dict[str, Any]:
    state = get_game_state(session_id)
    state.update(kwargs)
    set_game_state(session_id, state)
    return state


def _chat_key(session_id: str) -> str:
    return f"game:{session_id}:chat_buffer"


def push_chat_message(session_id: str, payload: Dict[str, Any]) -> None:
    key = _chat_key(session_id)
    redis_client.rpush(key, json.dumps(payload))
    redis_client.ltrim(key, -CHAT_BUFFER_MAX, -1)
    redis_client.expire(key, 86400)


def fetch_chat_buffer(session_id: str, start: int = 0, end: int = -1):
    key = _chat_key(session_id)
    return redis_client.lrange(key, start, end)


def trim_chat_buffer(session_id: str, keep_last: int) -> None:
    key = _chat_key(session_id)
    redis_client.ltrim(key, -keep_last, -1)


def rate_limit_allow(
    user_id: int,
    session_id: str,
    limit_per_minute: int,
) -> bool:
    rate_limit_key = f"rate:user:{user_id}:session:{session_id}"
    pipe = redis_client.pipeline()
    pipe.incr(rate_limit_key)
    pipe.expire(rate_limit_key, RATE_WINDOW_SEC)
    requests_count, _ignored_expire_result = pipe.execute()
    return int(requests_count) <= limit_per_minute


def _night_kill_key(session_id: str) -> str:
    return f"game:{session_id}:night_kill_target"


def set_night_kill_target(session_id: str, participant_id: int) -> None:
    redis_client.set(
        _night_kill_key(session_id),
        str(participant_id),
        ex=STATE_TTL_SEC,
    )


def get_and_clear_night_kill_target(session_id: str) -> int | None:
    key = _night_kill_key(session_id)
    raw = redis_client.get(key)
    redis_client.delete(key)
    if raw is None:
        return None

    return int(raw)


def get_night_kill_target(session_id: str) -> int | None:
    raw = redis_client.get(_night_kill_key(session_id))
    if raw is None:
        return None

    return int(raw)


def _night_heal_key(session_id: str) -> str:
    return f"game:{session_id}:night_heal_target"


def _night_check_key(session_id: str) -> str:
    return f"game:{session_id}:night_check_target"


def set_night_heal_target(session_id: str, participant_id: int) -> None:
    redis_client.set(
        _night_heal_key(session_id),
        str(participant_id),
        ex=STATE_TTL_SEC,
    )


def get_and_clear_night_heal_target(session_id: str) -> int | None:
    key = _night_heal_key(session_id)
    raw = redis_client.get(key)
    redis_client.delete(key)
    if raw is None:
        return None

    return int(raw)


def get_night_heal_target(session_id: str) -> int | None:
    raw = redis_client.get(_night_heal_key(session_id))
    if raw is None:
        return None

    return int(raw)


def set_night_check_target(session_id: str, participant_id: int) -> None:
    redis_client.set(
        _night_check_key(session_id),
        str(participant_id),
        ex=STATE_TTL_SEC,
    )


def get_and_clear_night_check_target(session_id: str) -> int | None:
    key = _night_check_key(session_id)
    raw = redis_client.get(key)
    redis_client.delete(key)
    if raw is None:
        return None

    return int(raw)


def get_night_check_target(session_id: str) -> int | None:
    raw = redis_client.get(_night_check_key(session_id))
    if raw is None:
        return None

    return int(raw)
