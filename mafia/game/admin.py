import django.contrib.admin

import game.models


@django.contrib.admin.register(game.models.GameSession)
class GameSessionAdmin(django.contrib.admin.ModelAdmin):
    list_display = ("slug", "status", "phase", "round", "seq", "created_at")
    list_filter = ("status", "phase")


@django.contrib.admin.register(game.models.Participant)
class ParticipantAdmin(django.contrib.admin.ModelAdmin):
    list_display = ("id", "session", "user", "role", "ready", "is_alive")
    list_filter = ("role", "ready", "is_alive")


@django.contrib.admin.register(game.models.TraitSnapshot)
class TraitSnapshotAdmin(django.contrib.admin.ModelAdmin):
    list_display = ("participant", "round", "created_at")


@django.contrib.admin.register(game.models.Evidence)
class EvidenceAdmin(django.contrib.admin.ModelAdmin):
    list_display = (
        "session",
        "round",
        "night",
        "evidence_class",
        "trait_layer",
    )


@django.contrib.admin.register(game.models.GameLog)
class GameLogAdmin(django.contrib.admin.ModelAdmin):
    list_display = ("id", "session", "participant", "created_at")


@django.contrib.admin.register(game.models.PollResult)
class PollResultAdmin(django.contrib.admin.ModelAdmin):
    list_display = ("session", "round", "voter", "target")


@django.contrib.admin.register(game.models.VoteRecord)
class VoteRecordAdmin(django.contrib.admin.ModelAdmin):
    list_display = ("session", "round", "voter", "target", "kind")


@django.contrib.admin.register(game.models.PlayerProfile)
class PlayerProfileAdmin(django.contrib.admin.ModelAdmin):
    list_display = ("user", "hints_enabled", "preferred_language")
