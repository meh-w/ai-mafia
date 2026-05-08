__all__ = ("validate_preparation_advance", "snapshot_traits_for_round")

import django.db.transaction

import game.constants
import game.models
import game.services.roles
import game.services.trait_quotas


def validate_preparation_advance(
    session: game.models.GameSession,
) -> list[str]:
    errors: list[str] = []
    participants = session.participants.all()
    required_players_count = session.max_players
    if participants.count() != required_players_count:
        errors.append(
            f"Нужно ровно {required_players_count} игроков",
        )
    if not all(participant.ready for participant in participants):
        errors.append("Не все отметили готовность")
    trait_validation_errors = game.services.trait_quotas.validate_trait_quotas(
        [participant.traits or {} for participant in participants],
        session.balance_config,
    )
    errors.extend(trait_validation_errors)
    return errors


@django.db.transaction.atomic
def snapshot_traits_for_round(
    session: game.models.GameSession, round_number: int
) -> None:
    for participant in session.participants.all():
        game.models.TraitSnapshot.objects.update_or_create(
            participant=participant,
            round=round_number,
            defaults={"traits": participant.traits or {}},
        )


def run_preparation_advance_side_effects(
    session: game.models.GameSession,
) -> None:
    game.services.roles.assign_roles(session)
    snapshot_traits_for_round(session, 1)
