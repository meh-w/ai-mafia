# Generated manually for domain MVP

import uuid

import django.db.models
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0002_session_ends_at_and_phase_lobby"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="gamesession",
            name="analytics_unreliable",
            field=models.BooleanField(
                default=False,
                verbose_name="дымовая завеса / ненадёжная аналитика",
            ),
        ),
        migrations.AddField(
            model_name="gamesession",
            name="informant_win_candidate",
            field=models.BooleanField(
                default=False,
                verbose_name="условие информатора выполнено",
            ),
        ),
        migrations.AddField(
            model_name="gamesession",
            name="investigation_70",
            field=models.BooleanField(
                default=False,
                verbose_name="порог 70% расследования (однократно)",
            ),
        ),
        migrations.AddField(
            model_name="gamesession",
            name="panic_70",
            field=models.BooleanField(
                default=False,
                verbose_name="порог 70% паники (однократно)",
            ),
        ),
        migrations.CreateModel(
            name="TraitSnapshot",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "round",
                    models.PositiveIntegerField(verbose_name="раунд"),
                ),
                (
                    "traits",
                    models.JSONField(
                        default=dict,
                        verbose_name="черты на раунд",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "participant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="trait_snapshots",
                        to="game.participant",
                        verbose_name="участник",
                    ),
                ),
            ],
            options={
                "unique_together": {("participant", "round")},
            },
        ),
        migrations.AddIndex(
            model_name="traitsnapshot",
            index=models.Index(
                fields=["participant", "round"],
                name="game_traits_particip_8a3b9f_idx",
            ),
        ),
        migrations.CreateModel(
            name="Evidence",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "round",
                    models.PositiveIntegerField(verbose_name="раунд"),
                ),
                (
                    "night",
                    models.PositiveIntegerField(
                        default=1,
                        verbose_name="номер ночи",
                    ),
                ),
                (
                    "trait_layer",
                    models.CharField(
                        max_length=32,
                        verbose_name="слой черты",
                    ),
                ),
                (
                    "evidence_class",
                    models.CharField(
                        choices=[
                            ("clean", "clean"),
                            ("standard", "standard"),
                            ("fake", "fake"),
                        ],
                        default="standard",
                        max_length=20,
                    ),
                ),
                ("is_fake", models.BooleanField(default=False)),
                (
                    "text_ui",
                    models.TextField(verbose_name="текст для UI"),
                ),
                (
                    "truth_json",
                    models.JSONField(
                        default=dict,
                        verbose_name="истина для сервера",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "planted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="planted_evidence",
                        to="game.participant",
                    ),
                ),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="evidence_items",
                        to="game.gamesession",
                        verbose_name="сессия",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="evidence",
            index=models.Index(
                fields=["session", "round"],
                name="game_eviden_session_e87ad4_idx",
            ),
        ),
        migrations.CreateModel(
            name="GameLog",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("text", models.TextField()),
                (
                    "sentiment_tag",
                    models.CharField(blank=True, max_length=50),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "participant",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="game_logs",
                        to="game.participant",
                    ),
                ),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="game_logs",
                        to="game.gamesession",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="gamelog",
            index=models.Index(
                fields=["session", "created_at"],
                name="game_gamelo_session_6f21a0_idx",
            ),
        ),
        migrations.CreateModel(
            name="PollResult",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("round", models.PositiveIntegerField()),
                ("values", models.JSONField(default=dict)),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="poll_results",
                        to="game.gamesession",
                    ),
                ),
                (
                    "target",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="polls_received",
                        to="game.participant",
                    ),
                ),
                (
                    "voter",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="polls_cast",
                        to="game.participant",
                    ),
                ),
            ],
            options={
                "unique_together": {
                    ("session", "round", "voter", "target"),
                },
            },
        ),
        migrations.CreateModel(
            name="VoteRecord",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("round", models.PositiveIntegerField()),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("natural", "natural"),
                            ("synthetic", "synthetic"),
                        ],
                        default="natural",
                        max_length=20,
                    ),
                ),
                (
                    "artifact_key",
                    models.CharField(blank=True, max_length=64),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "parent_vote",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="child_synthetic",
                        to="game.voterecord",
                    ),
                ),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="votes",
                        to="game.gamesession",
                    ),
                ),
                (
                    "target",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="votes_received",
                        to="game.participant",
                    ),
                ),
                (
                    "voter",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="votes_cast",
                        to="game.participant",
                    ),
                ),
            ],
            options={
                "unique_together": {("session", "round", "voter", "kind")},
            },
        ),
        migrations.AddIndex(
            model_name="voterecord",
            index=models.Index(
                fields=["session", "round"],
                name="game_votere_session_1c2d8e_idx",
            ),
        ),
    ]
