from __future__ import annotations

from typing import Any, Dict

__all__ = ("send_to_room_group",)


def send_to_room_group(
    session_id: str,
    handler_type: str,
    payload: Dict[str, Any],
) -> None:
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        f"room_{session_id}",
        {
            "type": handler_type,
            "payload": payload,
        },
    )
