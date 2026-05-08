__all__ = (
    "MIN_LOBBY_PLAYERS",
    "MAX_LOBBY_PLAYERS",
    "DEFAULT_LOBBY_PLAYERS",
    "MAX_SESSION_PLAYERS",
    "DEFAULT_PHASE_SECONDS",
    "PHASE_SECONDS",
    "PHASE_LOBBY",
    "PHASE_DAY_DISCUSSION",
    "PHASE_DAY_VOTE",
    "PHASE_NIGHT",
    "PHASE_FINISHED",
    "ROLE_MAFIA",
    "ROLE_SHERIFF",
    "ROLE_DOCTOR",
    "ROLE_CIVILIAN",
    "ROLE_CODES_CLASSIC",
    "TOWN_ROLE_CODES",
    "MAFIA_ROLE_CODES",
    "PHASE_PREPARATION",
    "role_codes_for_player_count",
)

PHASE_PREPARATION = "preparation"

MIN_LOBBY_PLAYERS = 4
MAX_LOBBY_PLAYERS = 15
DEFAULT_LOBBY_PLAYERS = 4

MAX_SESSION_PLAYERS = MAX_LOBBY_PLAYERS

DEFAULT_PHASE_SECONDS = 60

PHASE_LOBBY = "lobby"
PHASE_DAY_DISCUSSION = "day_discussion"
PHASE_DAY_VOTE = "day_vote"
PHASE_NIGHT = "night"
PHASE_FINISHED = "finished"

PHASE_SECONDS = {
    PHASE_LOBBY: 0,
    PHASE_PREPARATION: 120,
    PHASE_DAY_DISCUSSION: 120,
    PHASE_DAY_VOTE: 45,
    PHASE_NIGHT: 60,
    PHASE_FINISHED: 0,
}

ROLE_MAFIA = "mafia"
ROLE_SHERIFF = "sheriff"
ROLE_DOCTOR = "doctor"
ROLE_CIVILIAN = "civilian"

MAFIA_ROLE_CODES = frozenset({ROLE_MAFIA})
TOWN_ROLE_CODES = frozenset(
    {ROLE_SHERIFF, ROLE_DOCTOR, ROLE_CIVILIAN},
)


def role_codes_for_player_count(player_count: int) -> tuple[str, ...]:
    if player_count < MIN_LOBBY_PLAYERS or player_count > MAX_LOBBY_PLAYERS:
        raise ValueError(
            f"Число игроков должно быть от {MIN_LOBBY_PLAYERS} "
            f"до {MAX_LOBBY_PLAYERS}, получено {player_count}",
        )

    mafia_n = max(1, player_count // 3)
    civilians_n = player_count - mafia_n - 2
    if civilians_n < 1:
        raise ValueError(
            f"Для {player_count} игроков нельзя собрать состав "
            "(мафия + комиссар + доктор + мирные)",
        )

    roles: list[str] = [ROLE_MAFIA] * mafia_n
    roles.extend([ROLE_SHERIFF, ROLE_DOCTOR])
    roles.extend([ROLE_CIVILIAN] * civilians_n)
    if len(roles) != player_count:
        raise ValueError("внутренняя ошибка состава ролей")

    return tuple(roles)


ROLE_CODES_CLASSIC = role_codes_for_player_count(DEFAULT_LOBBY_PLAYERS)
