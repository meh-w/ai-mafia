__all__ = ("purchase_artifact",)


from typing import Any, Dict, Tuple

import game.models


def purchase_artifact(
    participant: game.models.Participant,
    artifact_key: str,
) -> Tuple[bool, Dict[str, Any]]:
    balance_config = participant.session.balance_config or {}
    artifacts_config = balance_config.get("artifacts", {})
    if artifact_key not in artifacts_config:
        return False, {"code": "unknown_artifact"}
    cost = int(artifacts_config[artifact_key].get("cost", 9999))
    inventory_items = list(participant.inventory or [])
    if artifact_key in inventory_items:
        return False, {"code": "already_owned"}
    if participant.ip_balance < cost:
        return False, {"code": "not_enough_ip"}
    participant.ip_balance -= cost
    inventory_items.append(artifact_key)
    participant.inventory = inventory_items
    participant.save(update_fields=["ip_balance", "inventory"])
    return True, {"cost": cost, "artifact": artifact_key}
