__all__ = ("resolve_classic_night",)

import logging
import secrets
from typing import Any, Dict, Optional

import django.db.transaction

import game.constants
from game.llm_client import get_llm_client
import game.models

logger = logging.getLogger(__name__)


def _send_private_result(
    session_id: str, user_id: int, payload: Dict[str, Any]
) -> None:
    import game.broadcasting

    print(f"📤 Sending private result to user {user_id}: {payload}")  # ОТЛАДКА

    game.broadcasting.send_to_room_group(
        session_id,
        "private.result",
        {"user_id": user_id, **payload},
    )


def _resolve_night_kill(
    session: game.models.GameSession,
    kill_id: int | None,
    heal_id: int | None,
) -> tuple[Optional[int], Optional[int], bool]:
    killed_id = None
    healed_id = None

    if heal_id:
        healed = game.models.Participant.objects.filter(
            pk=heal_id, session=session, is_alive=True
        ).first()
        if healed:
            healed_id = int(healed.pk)

    was_healed = False
    if kill_id:
        if kill_id == heal_id:
            was_healed = True
        else:
            victim = (
                game.models.Participant.objects.filter(
                    pk=kill_id, session=session, is_alive=True
                )
                .exclude(role__in=game.constants.MAFIA_ROLE_CODES)
                .first()
            )
            if victim:
                victim.is_alive = False
                victim.save(update_fields=["is_alive"])
                killed_id = int(victim.pk)

    return killed_id, healed_id, was_healed


def _create_ai_clue(
    session: game.models.GameSession, round_num: int, killer_traits: str = None
) -> None:
    if not killer_traits:
        clue_text = "Этой ночью тишина на улицах города не была нарушена."
    else:
        try:
            client = get_llm_client()

            if secrets.randbelow(100) < 25:
                fake_target = (
                    session.participants.filter(is_alive=True)
                    .exclude(role__in=game.constants.MAFIA_ROLE_CODES)
                    .order_by("?")
                    .first()
                )

                if fake_target:
                    fake_traits = fake_target.traits or {}
                    if isinstance(fake_traits, dict):
                        traits_str = ", ".join(fake_traits.values())
                    else:
                        traits_str = killer_traits
                else:
                    traits_str = killer_traits
            else:
                traits_str = killer_traits

            clue_text = client.generate_clue(traits_str)
        except Exception as e:
            logger.error(f"LLM failed: {e}")
            clue_text = "Свидетель заметил убегающую тень."

    game.models.Evidence.objects.create(
        session=session,
        round=round_num,
        night=round_num,
        owner=None,
        text_ui=clue_text,
        trait_layer="ai_clue",
    )


def _get_killer_traits(session: game.models.GameSession) -> Optional[str]:
    mafia_member = session.participants.filter(
        role=game.constants.ROLE_MAFIA, is_alive=True
    ).first()
    if not mafia_member or not mafia_member.traits:
        return None
    traits_dict = mafia_member.traits
    if isinstance(traits_dict, dict):
        return ", ".join(traits_dict.values())
    return None


def _get_target_name(
    session: game.models.GameSession, target_id: int | None
) -> Optional[str]:
    if not target_id:
        return None
    target = game.models.Participant.objects.filter(pk=target_id).first()
    return target.user.username if target else None


def _process_mafia_results(
    session: game.models.GameSession,
    session_id: str,
    kill_id: int | None,
    killed_id: int | None,
    was_healed: bool,
) -> None:
    mafiosi = session.participants.filter(
        role=game.constants.ROLE_MAFIA, is_alive=True
    )
    target_name = _get_target_name(session, kill_id)

    for m in mafiosi:
        result_payload = {
            "action": "kill",
            "success": killed_id is not None,
            "was_healed": was_healed,
            "target_name": target_name,
        }
        _send_private_result(session_id, m.user_id, result_payload)
        m.last_night_result = result_payload
        m.save(update_fields=["last_night_result"])


def _process_doctor_result(
    session: game.models.GameSession,
    session_id: str,
    heal_id: int | None,
    kill_id: int | None,
) -> None:
    doctor = session.participants.filter(
        role=game.constants.ROLE_DOCTOR, is_alive=True
    ).first()
    if not doctor:
        return

    target_name = _get_target_name(session, heal_id)
    result_payload = {
        "action": "heal",
        "success": heal_id is not None and heal_id == kill_id,
        "target_name": target_name,
    }
    _send_private_result(session_id, doctor.user_id, result_payload)
    doctor.last_night_result = result_payload
    doctor.save(update_fields=["last_night_result"])


def _process_sheriff_result(
    session: game.models.GameSession,
    session_id: str,
    check_id: int | None,
) -> None:
    if not check_id:
        return

    sheriff = session.participants.filter(
        role=game.constants.ROLE_SHERIFF, is_alive=True
    ).first()
    if not sheriff:
        return

    target = game.models.Participant.objects.get(pk=check_id)
    result_payload = {
        "action": "check",
        "target_name": target.user.username,
        "is_mafia": target.role in game.constants.MAFIA_ROLE_CODES,
    }
    _send_private_result(session_id, sheriff.user_id, result_payload)
    sheriff.last_night_result = result_payload
    sheriff.save(update_fields=["last_night_result"])


def resolve_classic_night(
    session: game.models.GameSession, night_round: int
) -> Dict[str, Any]:
    session_id = str(session.pk)

    import game.redis_store as rs

    kill_id = rs.get_and_clear_night_kill_target(session_id)
    heal_id = rs.get_and_clear_night_heal_target(session_id)
    check_id = rs.get_and_clear_night_check_target(session_id)

    with django.db.transaction.atomic():
        current_session = (
            game.models.GameSession.objects.select_for_update().get(
                pk=session.pk
            )
        )

        killed_id, healed_id, was_healed = _resolve_night_kill(
            current_session, kill_id, heal_id
        )

        killer_traits = _get_killer_traits(current_session)
        _create_ai_clue(current_session, night_round, killer_traits)

        session_id_str = str(current_session.pk)
        _process_mafia_results(
            current_session, session_id_str, kill_id, killed_id, was_healed
        )
        _process_doctor_result(
            current_session, session_id_str, heal_id, kill_id
        )
        _process_sheriff_result(current_session, session_id_str, check_id)

    return {"killed": killed_id, "healed": healed_id}
