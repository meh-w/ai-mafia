__all__ = (
    "tick_due_phases",
    "checkpoint_snapshot",
)

import json
import logging
from typing import Optional
import uuid

from celery import shared_task
import django.utils.timezone

from game.constants import (
    PHASE_DAY_DISCUSSION,
    PHASE_DAY_VOTE,
    PHASE_NIGHT,
    PHASE_PREPARATION,
)
import game.models
import game.redis_store

logger = logging.getLogger(__name__)

DUE_PHASES = (
    PHASE_NIGHT,
    PHASE_DAY_DISCUSSION,
    PHASE_DAY_VOTE,
    PHASE_PREPARATION,
)


def _chat_line_to_game_log(
    session: game.models.GameSession,
    raw: str,
) -> Optional[game.models.GameLog]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None

    message_id = data.get("id")
    if not message_id:
        return None

    if game.models.GameLog.objects.filter(pk=message_id).exists():
        return None

    author_user_id = data.get("user_id")
    author_participant = None
    if author_user_id:
        author_participant = game.models.Participant.objects.filter(
            session=session,
            user_id=author_user_id,
        ).first()

    return game.models.GameLog(
        id=uuid.UUID(message_id),
        session=session,
        participant=author_participant,
        text=data.get("text", "")[:10000],
        sentiment_tag="",
    )


def _due_sessions():
    now = django.utils.timezone.now()
    return game.models.GameSession.objects.filter(
        ends_at__isnull=False,
        ends_at__lte=now,
        phase__in=DUE_PHASES,
    ).exclude(status="finished")


def _checkpoint_sessions():
    return game.models.GameSession.objects.exclude(status="finished")[:20]


def _checkpoint_logs_for_session(
    session: game.models.GameSession,
) -> int:
    sid = str(session.pk)
    lines = game.redis_store.fetch_chat_buffer(sid, 0, 199)
    if not lines:
        return 0

    to_create = []
    for raw in lines:
        log = _chat_line_to_game_log(session, raw)
        if log is not None:
            to_create.append(log)

    if to_create:
        game.models.GameLog.objects.bulk_create(to_create)

    game.redis_store.trim_chat_buffer(sid, 500)
    return len(to_create)


@shared_task
def tick_due_phases():
    from game.fsm import transition_by_deadline

    due_sessions = _due_sessions()[:50]
    for session in due_sessions:
        try:
            transition_error = transition_by_deadline(str(session.pk))
        except Exception:
            logger.exception(
                "tick_due_phases failed for session",
                extra={"session_id": str(session.pk)},
            )
            continue

        if transition_error is not None:
            logger.warning(
                "tick_due_phases transition rejected",
                extra={
                    "session_id": str(session.pk),
                    "code": transition_error.code,
                    "error_message": transition_error.message,
                },
            )


@shared_task
def checkpoint_snapshot():
    for session in _checkpoint_sessions():
        _checkpoint_logs_for_session(session)

    return 0
