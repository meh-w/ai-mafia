__all__ = (
    "tally_votes_for_round",
    "apply_court_exclusion",
    "apply_day_vote_exclusion",
)

from collections import defaultdict
from typing import Any, Dict, List, Tuple

import django.db.transaction

import game.models


def tally_votes_for_round(
    session: game.models.GameSession,
    round_number: int,
) -> List[Tuple[int, int]]:
    vote_records = game.models.VoteRecord.objects.filter(
        session=session,
        round=round_number,
    )
    scores: Dict[int, int] = defaultdict(int)
    for vote_record in vote_records:
        vote_weight = (
            2
            if vote_record.kind == game.models.VoteRecord.KIND_SYNTHETIC
            else 1
        )
        scores[vote_record.target_id] += vote_weight

    return sorted(
        scores.items(),
        key=lambda score_by_target: (-score_by_target[1], score_by_target[0]),
    )


@django.db.transaction.atomic
def apply_court_exclusion(
    session: game.models.GameSession,
    round_number: int,
) -> Dict[str, Any]:
    ranked_scores = tally_votes_for_round(session, round_number)
    if not ranked_scores:
        return {"excluded": None}

    if len(ranked_scores) > 1 and ranked_scores[0][1] == ranked_scores[1][1]:
        return {
            "excluded_id": None,
            "scores": ranked_scores,
            "skipped_due_to_tie": True,
        }

    excluded_participant_id = ranked_scores[0][0]
    excluded_participant = (
        game.models.Participant.objects.select_for_update().get(
            pk=excluded_participant_id
        )
    )
    excluded_participant.is_alive = False
    excluded_participant.save(update_fields=["is_alive"])
    return {"excluded_id": excluded_participant_id, "scores": ranked_scores}


apply_day_vote_exclusion = apply_court_exclusion
