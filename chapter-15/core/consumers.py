"Beacon v0.15 — Collaboration Consumer (WebSocket)."
import logging
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from .crdt import TextCRDT, Char
logger = logging.getLogger("beacon.collab")

class CollaborationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.page_slug = self.scope["url_route"]["kwargs"]["slug"]
        self.group_name = f"collab_{self.page_slug}"
        self.user = self.scope["user"]
        if self.user.is_anonymous: await self.close(code=4001); return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        crdt = await self._load_crdt()
        await self.send_json({"type":"document_state","text":crdt.get_text()})

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content):
        op = content.get("op")
        if op == "insert":
            crdt = await self._load_crdt()
            nc = crdt.insert(char=content["char"], after_id=content["after_id"])
            await self._save_crdt(crdt)
            await self.channel_layer.group_send(self.group_name, {"type":"crdt.operation","op":"insert","char":nc.value,"char_id":nc.char_id,"after_id":nc.parent_id,"client_id":self.user.username,"lamport_ts":nc.lamport_ts})
        elif op == "delete":
            crdt = await self._load_crdt()
            crdt.delete(content["char_id"]); await self._save_crdt(crdt)
            await self.channel_layer.group_send(self.group_name, {"type":"crdt.operation","op":"delete","char_id":content["char_id"],"client_id":self.user.username})

    async def crdt_operation(self, event):
        crdt = await self._load_crdt()
        if event["op"] == "insert":
            crdt.merge(Char(char_id=event["char_id"],value=event["char"],parent_id=event["after_id"],client_id=event["client_id"],lamport_ts=event["lamport_ts"]))
        elif event["op"] == "delete": crdt.delete(event["char_id"])
        await self._save_crdt(crdt)
        await self.send_json({"type":"remote_op","op":event["op"],"char":event.get("char",""),"char_id":event.get("char_id",""),"after_id":event.get("after_id",""),"client_id":event.get("client_id","")})

    async def _load_crdt(self):
        from django.core.cache import cache
        key = f"crdt:{self.page_slug}"; data = await cache.aget(key)
        crdt = TextCRDT(site_id="server")
        if data:
            for cid, cd in data.items():
                crdt.chars[cid] = Char(char_id=cid,value=cd[0],parent_id=cd[1],client_id=cd[2],lamport_ts=cd[3])
        return crdt

    async def _save_crdt(self, crdt):
        from django.core.cache import cache
        key = f"crdt:{self.page_slug}"
        s = {cid:(c.value,c.parent_id,c.client_id,c.lamport_ts) for cid,c in crdt.chars.items()}
        await cache.aset(key, s, timeout=None)
