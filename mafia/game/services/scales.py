__all__ = (
    "clip_pct",
    "apply_event",
)

from typing import Any, Dict, Tuple

import game.models


def clip_pct(value: float, balance_config: Dict[str, Any]) -> float:
    scale_config = (balance_config or {}).get("scale", {})
    minimum_percent = float(scale_config.get("clip_min", 0))
    maximum_percent = float(scale_config.get("clip_max", 100))
    return max(minimum_percent, min(maximum_percent, value))


def apply_event(
    session: game.models.GameSession,
    event_key: str,
) -> Tuple[game.models.GameSession, Dict[str, Any]]:
    scale_config = (session.balance_config or {}).get("scale", {})
    detail: Dict[str, Any] = {"event": event_key}

    if event_key == "chat_toxicity_heuristic":
        delta = float(scale_config.get("panic_per_short_msg", 2))
        session.panic_pct = clip_pct(
            session.panic_pct + delta,
            session.balance_config,
        )
        detail["panic_delta"] = delta
    else:
        delta = float(scale_config.get(event_key, 0))
        session.investigation_pct = clip_pct(
            session.investigation_pct + delta,
            session.balance_config,
        )
        detail["investigation_delta"] = delta

    milestone = float(scale_config.get("scale_milestone_pct", 70))
    if session.investigation_pct >= milestone and not session.investigation_70:
        session.investigation_70 = True
    if session.panic_pct >= milestone and not session.panic_70:
        session.panic_70 = True

    detail["investigation_pct"] = session.investigation_pct
    detail["panic_pct"] = session.panic_pct

    session.save(
        update_fields=[
            "investigation_pct",
            "panic_pct",
            "investigation_70",
            "panic_70",
            "updated_at",
        ],
    )
    return session, detail
