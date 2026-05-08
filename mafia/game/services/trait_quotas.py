__all__ = ("validate_trait_quotas",)

from typing import Any, Dict, List


def validate_trait_quotas(
    participants_traits: List[Dict[str, Any]],
    balance_config: Dict[str, Any],
) -> List[str]:
    errors: List[str] = []
    quotas = (balance_config or {}).get("trait_quotas", {})
    for idx, traits in enumerate(participants_traits):
        prefix = f"Игрок {idx + 1}"
        for layer in ("L1", "L2", "L3", "L4"):
            layer_cfg = quotas.get(layer, {"min_tags": 1, "max_tags": 2})
            min_tags = int(layer_cfg.get("min_tags", 1))
            max_tags = int(layer_cfg.get("max_tags", 2))
            raw_layer_traits = traits.get(layer, [])
            selected_tags_count = (
                len(raw_layer_traits)
                if isinstance(raw_layer_traits, list)
                else 0
            )
            if (
                selected_tags_count < min_tags
                or selected_tags_count > max_tags
            ):
                errors.append(
                    f"{prefix}: слой {layer} — ожидалось "
                    f"{min_tags}…{max_tags} тегов, сейчас "
                    f"{selected_tags_count}",
                )
    return errors
