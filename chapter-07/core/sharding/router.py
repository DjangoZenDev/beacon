
"""
Beacon v0.7 — Organization Shard Router

Django database router that routes queries to the correct shard based
on the organization_id. Carried forward from Chapter 6.
"""

import logging
import threading

from django.conf import settings

from .ring_manager import ring_manager

logger = logging.getLogger("beacon.sharding")

_thread_locals = threading.local()


def use_primary_for_request():
    _thread_locals.use_primary = True


def _should_use_primary():
    return getattr(_thread_locals, "use_primary", False)


class OrganizationShardRouter:

    def db_for_read(self, model, **hints):
        if _should_use_primary():
            shard = self._resolve_shard(model, **hints)
            return shard or "default"
        shard = self._resolve_shard(model, **hints)
        if shard and shard in getattr(settings, "SHARD_MAP", {}):
            replica_alias = f"{shard}-replica"
            if replica_alias in settings.DATABASES:
                return replica_alias
        return shard or "default"

    def db_for_write(self, model, **hints):
        return self._resolve_shard(model, **hints) or "default"

    def allow_relation(self, obj1, obj2, **hints):
        org1 = self._get_organization_id(obj1)
        org2 = self._get_organization_id(obj2)
        if org1 is not None and org2 is not None:
            return org1 == org2
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == "default":
            return True
        if db in getattr(settings, "SHARD_MAP", {}):
            return True
        return False

    def _resolve_shard(self, model, **hints):
        org_id = None
        if "organization_id" in hints:
            org_id = hints["organization_id"]
        elif "instance" in hints:
            org_id = self._get_organization_id(hints["instance"])
        if org_id is None:
            logger.debug("Cannot determine shard for %s", model.__name__ if model else "unknown")
            return None
        try:
            return ring_manager.get_shard(org_id)
        except Exception:
            logger.warning("Ring lookup failed for org_id=%s", org_id)
            return "default"

    @staticmethod
    def _get_organization_id(obj):
        if hasattr(obj, "organization_id"):
            return obj.organization_id
        try:
            return obj._meta.get_field("organization_id").value_from_object(obj)
        except Exception:
            return None
