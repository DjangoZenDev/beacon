"""
Beacon v0.9 — Collaboration Consumer (WebSocket)

Handles real-time collaborative editing for a single user's WebSocket
connection. On connect: joins a channel group for the page. On receive:
applies CRDT operations locally, persists to Redis, and broadcasts to
all other consumers in the group.

The CRDT state for each page lives in Redis (not in consumer memory)
so that it survives restarts and is accessible from any server.

Chapter 9, Principle 3: "The channel layer is a message bus."
Chapter 9, Principle 4: "Separate document state from delivery state."
"""

import json
import logging

from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .crdt import TextCRDT, Char

logger = logging.getLogger("beacon.collab")


class CollaborationConsumer(AsyncJsonWebsocketConsumer):
    """
    Handles a single user's WebSocket connection to a collaborative page.

    Operations handled:
      - {"op": "insert", "char": "x", "after_id": "..."}
      - {"op": "delete", "char_id": "..."}
      - {"op": "cursor", "position": 42}
    """

    async def connect(self):
        """Accept the WebSocket connection and join the page's group."""
        self.page_slug = self.scope["url_route"]["kwargs"]["slug"]
        self.group_name = f"collab_{self.page_slug}"
        self.user = self.scope["user"]

        # Reject unauthenticated users.
        if self.user.is_anonymous:
            await self.close(code=4001)
            return

        # Join the collaboration group for this page.
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send the current document state to the newly connected client.
        crdt = await self._load_crdt()
        await self.send_json({
            "type": "document_state",
            "text": crdt.get_text(),
        })

        logger.info(
            "WebSocket connected: user=%s page=%s group=%s",
            self.user.username, self.page_slug, self.group_name,
        )

    async def disconnect(self, close_code):
        """Leave the page's group on disconnect."""
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info(
            "WebSocket disconnected: user=%s page=%s code=%s",
            self.user.username, self.page_slug, close_code,
        )

    async def receive_json(self, content):
        """
        Process an incoming CRDT operation from the client.

        Dispatches to the appropriate handler based on `op` field.
        """
        op_type = content.get("op")

        if op_type == "insert":
            await self._handle_insert(content)
        elif op_type == "delete":
            await self._handle_delete(content)
        elif op_type == "cursor":
            await self._broadcast_cursor(content)
        else:
            logger.warning("Unknown op type: %s", op_type)

    async def _handle_insert(self, content: dict):
        """Apply a character insertion and broadcast to the group."""
        crdt = await self._load_crdt()
        new_char = crdt.insert(
            char=content["char"],
            after_id=content["after_id"],
        )
        await self._save_crdt(crdt)

        # Broadcast to all clients in the group (including this one).
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "crdt.operation",
                "op": "insert",
                "char": new_char.value,
                "char_id": new_char.char_id,
                "after_id": new_char.parent_id,
                "client_id": self.user.username,
                "lamport_ts": new_char.lamport_ts,
            },
        )

    async def _handle_delete(self, content: dict):
        """Apply a character deletion and broadcast to the group."""
        crdt = await self._load_crdt()
        crdt.delete(content["char_id"])
        await self._save_crdt(crdt)

        # Broadcast deletion to all clients in the group.
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "crdt.operation",
                "op": "delete",
                "char_id": content["char_id"],
                "client_id": self.user.username,
            },
        )

    async def _broadcast_cursor(self, content: dict):
        """Broadcast cursor position to other collaborators."""
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "cursor.update",
                "client_id": self.user.username,
                "position": content.get("position", 0),
            },
        )

    async def crdt_operation(self, event: dict):
        """
        Handler for crdt.operation events from the channel layer.

        Called on every consumer in the group (including the sender)
        when someone makes a change. Applies the remote operation to
        the local CRDT state (in Redis) and forwards to the client.
        """
        op = event["op"]

        if op == "insert":
            # Apply the remote operation to our local CRDT copy.
            crdt = await self._load_crdt()
            remote_char = Char(
                char_id=event["char_id"],
                value=event["char"],
                parent_id=event["after_id"],
                client_id=event["client_id"],
                lamport_ts=event["lamport_ts"],
            )
            crdt.merge(remote_char)
            await self._save_crdt(crdt)

        elif op == "delete":
            crdt = await self._load_crdt()
            crdt.delete(event["char_id"])
            await self._save_crdt(crdt)

        # Forward to the WebSocket client.
        await self.send_json({
            "type": "remote_op",
            "op": event["op"],
            "char": event.get("char", ""),
            "char_id": event.get("char_id", ""),
            "after_id": event.get("after_id", ""),
            "client_id": event.get("client_id", ""),
        })

    async def cursor_update(self, event: dict):
        """
        Handler for cursor.update events from the channel layer.

        Forwards cursor position to the WebSocket client so they
        can render remote collaborator cursors.
        """
        await self.send_json({
            "type": "cursor",
            "client_id": event["client_id"],
            "position": event["position"],
        })

    async def _load_crdt(self) -> TextCRDT:
        """
        Load the CRDT state for this page from the Django cache (Redis).

        The CRDT chars dict is stored as a JSON-serializable mapping
        of char_id -> (value, parent_id, client_id, lamport_ts).
        """
        from django.core.cache import cache

        key = f"crdt:{self.page_slug}"
        data = await cache.aget(key)
        crdt = TextCRDT(site_id="server")

        if data:
            # Reconstruct Char objects from serialized tuples.
            for char_id, char_data in data.items():
                crdt.chars[char_id] = Char(
                    char_id=char_id,
                    value=char_data[0],
                    parent_id=char_data[1],
                    client_id=char_data[2],
                    lamport_ts=char_data[3],
                )

        return crdt

    async def _save_crdt(self, crdt: TextCRDT):
        """
        Persist the CRDT state to the Django cache (Redis).

        Stores a lightweight serialization: a dict of
        char_id -> (value, parent_id, client_id, lamport_ts).
        """
        from django.core.cache import cache

        key = f"crdt:{self.page_slug}"
        serialized = {}
        for char_id, c in crdt.chars.items():
            serialized[char_id] = (c.value, c.parent_id, c.client_id, c.lamport_ts)

        await cache.aset(key, serialized, timeout=None)  # No expiry
