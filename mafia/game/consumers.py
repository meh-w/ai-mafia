__all__ = ("GameConsumer",)


from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
import django.core.exceptions
import django.utils.timezone

import game.models
import game.services.chat
import game.services.hints
import game.services.night_ws
from game.services.win_conditions import MAFIA_ROLES


class GameConsumer(AsyncJsonWebsocketConsumer):
    async def private_result(self, event):
        payload = event.get("payload", {})
        target_user_id = payload.get("user_id")

        if target_user_id is not None:
            target_user_id = int(target_user_id)

        my_user_id = self.scope["user"].id

        if target_user_id == my_user_id:
            clean_payload = {
                k: v for k, v in payload.items() if k != "user_id"
            }
            await self.send_json(
                {"type": "private.result", "payload": clean_payload}
            )
            print(f"SENT private.result to user {target_user_id}")
        else:
            print(f"SKIPPED for user {my_user_id}")

    async def connect(self):
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        user = self.scope["user"]
        if not user.is_authenticated:
            await self.close(code=4401)
            return
        if not await self.is_member(user.id, self.session_id):
            await self.close(code=4403)
            return
        self.group_name = f"room_{self.session_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        self.mafia_group_name = None
        if await self.is_mafia(user.id, self.session_id):
            self.mafia_group_name = f"room_mafia_{self.session_id}"
            await self.channel_layer.group_add(
                self.mafia_group_name,
                self.channel_name,
            )
        await self.accept()
        payload = await self.session_joined_payload()
        await self.send_json({"type": "session.joined", "payload": payload})

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name,
            )
        if getattr(self, "mafia_group_name", None):
            await self.channel_layer.group_discard(
                self.mafia_group_name,
                self.channel_name,
            )

    async def receive_json(self, content):
        msg_type = content.get("type")
        if msg_type == "ping":
            await self._send_pong()
            return
        if msg_type == "chat.message":
            await self._receive_public_chat(content)
            return
        if msg_type == "night.target":
            await self._receive_night_pick(
                content,
                game.services.night_ws.set_kill_target_from_ws,
                "night.target.ack",
            )
            return
        if msg_type == "night.action":
            await self._receive_night_action(content)
            return
        await self.send_json(
            {
                "type": "error",
                "payload": {"code": "unknown_type", "message": str(msg_type)},
            },
        )

    async def _send_pong(self):
        await self.send_json(
            {
                "type": "pong",
                "payload": {"ts": django.utils.timezone.now().isoformat()},
            },
        )

    async def _receive_public_chat(self, content):
        text = (content.get("payload") or {}).get("text", "")
        ok, info = await database_sync_to_async(
            game.services.chat.append_public_chat_message,
        )(self.session_id, self.scope["user"].id, text)
        if not ok:
            await self.send_json({"type": "error", "payload": info})

    async def _receive_night_pick(self, content, setter, ack_type):
        payload_data = content.get("payload") or {}
        target_id = payload_data.get("target_id")
        if not target_id:
            await self.send_json(
                {"type": "error", "payload": {"code": "bad_payload"}},
            )
            return
        try:
            ok, info = await database_sync_to_async(setter)(
                self.session_id,
                self.scope["user"].id,
                str(target_id),
            )
        except (
            game.models.Participant.DoesNotExist,
            game.models.GameSession.DoesNotExist,
            ValueError,
            django.core.exceptions.ValidationError,
        ):
            await self.send_json(
                {"type": "error", "payload": {"code": "bad_target"}},
            )
            return
        if not ok:
            await self.send_json({"type": "error", "payload": info})
        else:
            await self.send_json({"type": ack_type, "payload": {}})

    async def _receive_night_action(self, content):
        payload_data = content.get("payload") or {}
        action_kind = payload_data.get("kind")
        target_id = payload_data.get("target_id")
        if not action_kind or not target_id:
            await self.send_json(
                {"type": "error", "payload": {"code": "bad_payload"}},
            )
            return
        try:
            ok, info = await database_sync_to_async(
                game.services.night_ws.set_night_action_from_ws,
            )(
                self.session_id,
                self.scope["user"].id,
                str(action_kind),
                str(target_id),
            )
        except (
            game.models.Participant.DoesNotExist,
            game.models.GameSession.DoesNotExist,
            ValueError,
            django.core.exceptions.ValidationError,
        ):
            await self.send_json(
                {"type": "error", "payload": {"code": "bad_target"}},
            )
            return
        if not ok:
            await self.send_json({"type": "error", "payload": info})
        else:
            await self.send_json(
                {
                    "type": "night.action.ack",
                    "payload": {"kind": str(action_kind)},
                },
            )

    async def chat_message(self, event):
        await self.send_json(
            {"type": "chat.message", "payload": event["payload"]},
        )

    async def phase_changed(self, event):
        base = dict(event["payload"])
        extra = await self._hint_payload_for_socket()
        merged = {**base, **extra}
        await self.send_json(
            {"type": "phase_changed", "payload": merged},
        )

    async def votes_updated(self, event):
        await self.send_json(
            {
                "type": "votes_updated",
                "payload": event.get("payload") or {},
            },
        )

    async def lobby_roster(self, event):
        await self.send_json(
            {
                "type": "lobby.roster",
                "payload": event.get("payload") or {},
            },
        )

    @database_sync_to_async
    def is_member(self, user_id, session_id):
        return game.models.Participant.objects.filter(
            user_id=user_id,
            session_id=session_id,
        ).exists()

    @database_sync_to_async
    def is_mafia(self, user_id, session_id):
        participant = (
            game.models.Participant.objects.filter(
                user_id=user_id,
                session_id=session_id,
            )
            .only("role")
            .first()
        )
        return bool(participant and participant.role in MAFIA_ROLES)

    @database_sync_to_async
    def session_joined_payload(self):
        session = game.models.GameSession.objects.get(pk=self.session_id)
        user = self.scope["user"]
        participant = game.models.Participant.objects.get(
            session=session,
            user=user,
        )

        payload = {
            "seq": session.seq,
            "phase": session.phase,
            "round": session.round,
            "ends_at": (
                session.ends_at.isoformat() if session.ends_at else None
            ),
            "last_night_result": participant.last_night_result,
        }

        if session.win_summary:
            payload["win_summary"] = session.win_summary

        payload.update(
            game.services.hints.build_hint_payload_for_player(
                user,
                session,
                participant,
            ),
        )
        return payload

    @database_sync_to_async
    def _hint_payload_for_socket(self):
        session = game.models.GameSession.objects.get(pk=self.session_id)
        user = self.scope["user"]
        participant = game.models.Participant.objects.get(
            session=session,
            user=user,
        )
        return game.services.hints.build_hint_payload_for_player(
            user,
            session,
            participant,
        )
