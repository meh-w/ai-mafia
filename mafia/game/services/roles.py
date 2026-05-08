__all__ = ("assign_roles_classic",)

import secrets

import django.db.transaction

import game.constants
import game.models


def assign_roles_classic(session: game.models.GameSession) -> None:
    with django.db.transaction.atomic():
        participants = list(
            game.models.Participant.objects.select_for_update().filter(
                session=session,
            ),
        )
        required_players_count = session.max_players
        if len(participants) != required_players_count:
            raise ValueError(
                f"Требуется {required_players_count} участников",
            )
        if any(participant.role for participant in participants):
            return
        role_codes = list(
            game.constants.role_codes_for_player_count(
                required_players_count,
            ),
        )
        randomizer = secrets.SystemRandom()
        randomizer.shuffle(participants)
        for participant, role_code in zip(participants, role_codes):
            participant.role = role_code
            participant.save(update_fields=["role"])
