"""Beacon v0.10 — Org Shard Router."""
import logging, threading
from django.conf import settings
from .ring_manager import ring_manager
logger = logging.getLogger("beacon.sharding")
_tl = threading.local()

def use_primary_for_request(): _tl.use_primary = True

class OrganizationShardRouter:
    def db_for_read(self, model, **hints):
        shard = self._resolve(model, **hints)
        if getattr(_tl,"use_primary",False): return shard or "default"
        if shard and shard in getattr(settings,"SHARD_MAP",{}):
            ra = f"{shard}-replica"
            if ra in settings.DATABASES: return ra
        return shard or "default"
    def db_for_write(self, model, **hints): return self._resolve(model, **hints) or "default"
    def allow_relation(self, obj1, obj2, **hints):
        o1 = self._org_id(obj1); o2 = self._org_id(obj2)
        return o1 == o2 if (o1 is not None and o2 is not None) else True
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return db == "default" or db in getattr(settings,"SHARD_MAP",{})
    def _resolve(self, model, **hints):
        org_id = hints.get("organization_id")
        if org_id is None and "instance" in hints: org_id = self._org_id(hints["instance"])
        if org_id is None: return None
        try: return ring_manager.get_shard(org_id)
        except Exception: return "default"
    @staticmethod
    def _org_id(obj):
        if hasattr(obj,"organization_id"): return obj.organization_id
        try: return obj._meta.get_field("organization_id").value_from_object(obj)
        except Exception: return None
