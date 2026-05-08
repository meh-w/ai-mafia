__all__ = ("load_default_balance_config",)

import json
from pathlib import Path

import game.constants


def load_default_balance_config():
    path = (
        Path(__file__).resolve().parent / "fixtures" / "balance_default.json"
    )
    with path.open(encoding="utf-8") as fh:
        balance = json.load(fh)

    balance["default_phase_seconds"] = game.constants.DEFAULT_PHASE_SECONDS
    balance["phase_seconds"] = dict(game.constants.PHASE_SECONDS)
    return balance
