__all__ = (
    "GameSession",
    "Participant",
    "PlayerProfile",
    "TraitSnapshot",
    "Evidence",
    "GameLog",
    "PollResult",
    "VoteRecord",
)

import uuid

import django.core.validators
import django.db.models

import game.constants


class GameSession(django.db.models.Model):
    id = django.db.models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    slug = django.db.models.SlugField(
        unique=True,
        max_length=50,
        blank=True,
    )

    status = django.db.models.CharField(
        max_length=20,
        default="lobby",
        verbose_name="статус",
        help_text="жизненный цикл: lobby, active, finished",
    )
    phase = django.db.models.CharField(
        max_length=20,
        default="lobby",
        verbose_name="фаза",
        help_text=(
            "lobby, day_discussion, day_vote, night, finished (классика)"
        ),
    )

    round = django.db.models.PositiveIntegerField(
        default=0,
        verbose_name="раунд",
    )
    seq = django.db.models.BigIntegerField(
        default=0,
        verbose_name="счётчик событий",
    )

    balance_config = django.db.models.JSONField(
        default=dict,
        verbose_name="конфиг баланса",
    )
    analytics_language = django.db.models.CharField(
        max_length=10,
        default="ru",
        verbose_name="язык аналитики",
    )

    investigation_pct = django.db.models.FloatField(
        default=0.0,
        verbose_name="шкала расследования",
    )
    panic_pct = django.db.models.FloatField(
        default=0.0,
        verbose_name="шкала паники",
    )
    investigation_70 = django.db.models.BooleanField(
        default=False,
        verbose_name="порог 70% расследования (однократно)",
    )
    panic_70 = django.db.models.BooleanField(
        default=False,
        verbose_name="порог 70% паники (однократно)",
    )
    analytics_unreliable = django.db.models.BooleanField(
        default=False,
        verbose_name="дымовая завеса / ненадёжная аналитика",
    )
    informant_win_candidate = django.db.models.BooleanField(
        default=False,
        verbose_name="условие информатора выполнено",
    )
    win_summary = django.db.models.JSONField(
        default=dict,
        blank=True,
        verbose_name="итог победы",
    )

    created_at = django.db.models.DateTimeField(
        auto_now_add=True,
        verbose_name="создана",
    )
    updated_at = django.db.models.DateTimeField(
        auto_now=True,
        verbose_name="обновлена",
    )
    ends_at = django.db.models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="окончание текущей фазы",
    )
    doctor_last_healed = django.db.models.ForeignKey(
        "Participant",
        null=True,
        blank=True,
        on_delete=django.db.models.SET_NULL,
        related_name="doctor_last_heal_sessions",
        verbose_name="последний игрок, которого лечил доктор",
    )
    max_players = django.db.models.PositiveSmallIntegerField(
        default=game.constants.DEFAULT_LOBBY_PLAYERS,
        verbose_name="игроков за столом",
        help_text="размер лобби до старта партии (классика)",
        validators=[
            django.core.validators.MinValueValidator(
                game.constants.MIN_LOBBY_PLAYERS,
            ),
            django.core.validators.MaxValueValidator(
                game.constants.MAX_LOBBY_PLAYERS,
            ),
        ],
    )

    class Meta:
        verbose_name = "игровая сессия"
        verbose_name_plural = "игровые сессии"

    def __str__(self):
        return f"Game {self.slug or self.id}"


class Participant(django.db.models.Model):
    session = django.db.models.ForeignKey(
        GameSession,
        on_delete=django.db.models.CASCADE,
        related_name="participants",
        verbose_name="сессия",
    )
    user = django.db.models.ForeignKey(
        "auth.User",
        on_delete=django.db.models.CASCADE,
        verbose_name="пользователь",
    )

    role = django.db.models.CharField(
        max_length=50,
        blank=True,
        verbose_name="роль",
    )
    is_alive = django.db.models.BooleanField(
        default=True,
        verbose_name="жив",
    )

    ready = django.db.models.BooleanField(
        default=False,
        verbose_name="готов",
    )

    traits = django.db.models.JSONField(
        default=dict,
        blank=True,
        verbose_name="приметы игрока",
    )
    ip_balance = django.db.models.IntegerField(
        default=0,
        verbose_name="очки внимания",
    )
    inventory = django.db.models.JSONField(
        default=list,
        blank=True,
        verbose_name="инвентарь",
    )
    sheriff_checks = django.db.models.JSONField(
        default=list,
        blank=True,
        verbose_name="результаты проверок комиссара",
    )

    doctor_last_result = django.db.models.JSONField(default=dict, blank=True)

    mafia_last_kill = django.db.models.JSONField(default=dict, blank=True)

    last_night_result = django.db.models.JSONField(
        default=dict,
        blank=True,
        verbose_name="результат последней ночи",
    )

    class Meta:
        unique_together = [["session", "user"]]
        verbose_name = "участник"
        verbose_name_plural = "участники"

    def __str__(self):
        return (
            f"{self.user.username} in {self.session.slug or self.session.id}"
        )


class PlayerProfile(django.db.models.Model):
    user = django.db.models.OneToOneField(
        "auth.User",
        on_delete=django.db.models.CASCADE,
        related_name="player_profile",
        verbose_name="пользователь",
    )
    hints_enabled = django.db.models.BooleanField(
        default=True,
        verbose_name="показывать подсказки",
    )
    preferred_language = django.db.models.CharField(
        max_length=2,
        default="ru",
        verbose_name="язык подсказок",
    )

    class Meta:
        verbose_name = "профиль игрока"
        verbose_name_plural = "профили игроков"

    def __str__(self):
        return f"Profile({self.user_id})"


class TraitSnapshot(django.db.models.Model):
    participant = django.db.models.ForeignKey(
        Participant,
        on_delete=django.db.models.CASCADE,
        related_name="trait_snapshots",
        verbose_name="участник",
    )
    round = django.db.models.PositiveIntegerField(
        verbose_name="раунд",
    )
    traits = django.db.models.JSONField(
        default=dict,
        verbose_name="черты на раунд",
    )
    created_at = django.db.models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        unique_together = [["participant", "round"]]
        indexes = [
            django.db.models.Index(
                fields=["participant", "round"],
            ),
        ]


class Evidence(django.db.models.Model):
    CLASS_CLEAN = "clean"
    CLASS_STANDARD = "standard"
    CLASS_FAKE = "fake"
    CLASS_CHOICES = (
        (CLASS_CLEAN, "clean"),
        (CLASS_STANDARD, "standard"),
        (CLASS_FAKE, "fake"),
    )

    session = django.db.models.ForeignKey(
        GameSession,
        on_delete=django.db.models.CASCADE,
        related_name="evidences",
    )
    round = django.db.models.PositiveIntegerField(verbose_name="раунд")
    night = django.db.models.PositiveIntegerField(
        default=1,
        verbose_name="номер ночи",
    )
    trait_layer = django.db.models.CharField(
        max_length=32,
        verbose_name="слой черты",
    )
    evidence_class = django.db.models.CharField(
        max_length=20,
        choices=CLASS_CHOICES,
        default=CLASS_STANDARD,
    )
    is_fake = django.db.models.BooleanField(default=False)
    planted_by = django.db.models.ForeignKey(
        Participant,
        null=True,
        blank=True,
        on_delete=django.db.models.SET_NULL,
        related_name="planted_evidence",
    )
    text_ui = django.db.models.TextField(verbose_name="текст для UI")
    truth_json = django.db.models.JSONField(
        default=dict,
        verbose_name="истина для сервера",
    )
    created_at = django.db.models.DateTimeField(auto_now_add=True)

    owner = django.db.models.ForeignKey(
        "Participant",
        on_delete=django.db.models.CASCADE,
        related_name="evidences",
        null=True,
        blank=True,
        verbose_name="владелец улики",
    )

    class Meta:
        indexes = [
            django.db.models.Index(fields=["session", "round"]),
        ]


class GameLog(django.db.models.Model):
    id = django.db.models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    session = django.db.models.ForeignKey(
        GameSession,
        on_delete=django.db.models.CASCADE,
        related_name="game_logs",
    )
    participant = django.db.models.ForeignKey(
        Participant,
        null=True,
        blank=True,
        on_delete=django.db.models.SET_NULL,
        related_name="game_logs",
    )
    text = django.db.models.TextField()
    sentiment_tag = django.db.models.CharField(max_length=50, blank=True)
    created_at = django.db.models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            django.db.models.Index(fields=["session", "created_at"]),
        ]


class PollResult(django.db.models.Model):
    session = django.db.models.ForeignKey(
        GameSession,
        on_delete=django.db.models.CASCADE,
        related_name="poll_results",
    )
    round = django.db.models.PositiveIntegerField()
    voter = django.db.models.ForeignKey(
        Participant,
        on_delete=django.db.models.CASCADE,
        related_name="polls_cast",
    )
    target = django.db.models.ForeignKey(
        Participant,
        on_delete=django.db.models.CASCADE,
        related_name="polls_received",
    )
    values = django.db.models.JSONField(default=dict)

    class Meta:
        unique_together = [["session", "round", "voter"]]


class VoteRecord(django.db.models.Model):
    KIND_NATURAL = "natural"
    KIND_SYNTHETIC = "synthetic"
    KIND_CHOICES = (
        (KIND_NATURAL, "natural"),
        (KIND_SYNTHETIC, "synthetic"),
    )

    session = django.db.models.ForeignKey(
        GameSession,
        on_delete=django.db.models.CASCADE,
        related_name="votes",
    )
    round = django.db.models.PositiveIntegerField()
    voter = django.db.models.ForeignKey(
        Participant,
        on_delete=django.db.models.CASCADE,
        related_name="votes_cast",
    )
    target = django.db.models.ForeignKey(
        Participant,
        on_delete=django.db.models.CASCADE,
        related_name="votes_received",
    )
    kind = django.db.models.CharField(
        max_length=20,
        choices=KIND_CHOICES,
        default=KIND_NATURAL,
    )
    artifact_key = django.db.models.CharField(max_length=64, blank=True)
    parent_vote = django.db.models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=django.db.models.SET_NULL,
        related_name="child_synthetic",
    )
    created_at = django.db.models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["session", "round", "voter", "kind"]]
        indexes = [
            django.db.models.Index(fields=["session", "round"]),
        ]
