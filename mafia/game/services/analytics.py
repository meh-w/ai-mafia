__all__ = (
    "aggregate_polls_for_round",
    "apply_poll_consensus_to_scale",
)

from typing import Any, Dict

import game.models
import game.services.scales


def aggregate_polls_for_round(
    session: game.models.GameSession,
    round_number: int,
) -> Dict[str, Any]:
    poll_results = list(
        game.models.PollResult.objects.filter(
            session=session,
            round=round_number,
        ).select_related("voter__user", "target__user"),
    )
    aggregated_payload: Dict[str, Any] = {
        "round": round_number,
        "count": len(poll_results),
        "answers": [],
    }
    for poll_result in poll_results:
        answer_values = poll_result.values or {}
        aggregated_payload["answers"].append(
            {
                "voter": poll_result.voter.user.username,
                "target": poll_result.target.user.username,
                "aggression": answer_values.get("aggression"),
                "defense": answer_values.get("defense"),
                "mention": answer_values.get("mention"),
            },
        )
    return aggregated_payload


def apply_poll_consensus_to_scale(
    session: game.models.GameSession,
    round_number: int,
) -> None:
    poll_results = game.models.PollResult.objects.filter(
        session=session,
        round=round_number,
    )
    if not poll_results.exists():
        return
    answer_values_list = [
        poll_result.values or {} for poll_result in poll_results
    ]
    mean_scores = []
    for answer_values in answer_values_list:
        try:
            aggression = int(answer_values.get("aggression", 0))
            defense = int(answer_values.get("defense", 0))
            mention = int(answer_values.get("mention", 0))
        except (TypeError, ValueError):
            continue
        mean_scores.append((aggression + defense + mention) / 3.0)
    if len(mean_scores) < 2:
        return
    spread = max(mean_scores) - min(mean_scores)
    if spread <= 1.0:
        game.services.scales.apply_event(session, "poll_consensus_bonus")
