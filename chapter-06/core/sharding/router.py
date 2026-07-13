"""
Beacon v0.6 — Organization Shard Router

Django database router that routes queries to the correct shard based
on the organization_id. Replaces ReadReplicaRouter from Chapter 5.

The router combines shard routing with read-replica routing:
- Writes: go to the primary of the shard that owns the organization.
- Reads: go to the replica of that shard, unless use_primary_for_request()
  was called (read-after-write consistency).

How the shard is determined:
1. If the model has an organization_id field, use its value.
2. If the hints dictionary contains an "organization_id", use that.
3. If the instance has an organization_id attribute, use that.
4. Otherwise, fall back to "default".

The consistent hash ring is obtained from ring_manager.get_ring(),
which is kept in sync via etcd3.
"""

import logging
import threading

from django.conf import settings

from .ring_manager import ring_manager

logger = logging.getLogger("beacon.sharding")

# ── Thread-local for read-after-write consistency ────────────────
# Retained from Chapter 5: when a request writes and then reads,
# force reads to the primary to avoid replication lag.
_thread_locals = threading.local()


def use_primary_for_request():
    """Force all subsequent reads in this request to use the primary."""
    _thread_locals.use_primary = True


def _should_use_primary():
    return getattr(_thread_locals, "use_primary", False)


class OrganizationShardRouter:
    """
    Route database operations to the correct shard by organization_id.

    Combines two routing concerns:
    1. Shard routing (which database has this organization's data?)
    2. Read/write splitting (primary for writes, replica for reads)
    """

    # ── Read routing ─────────────────────────────────────────────

    def db_for_read(self, model, **hints):
        """
        Route reads to the correct shard.

        Returns "replica" if we should read from a replica (Chapter 5
        behavior), otherwise routes to the shard primary. The actual
        shard lookup for replicas is handled by the SHARD_REPLICA_MAP
        in settings.
        """
        if _should_use_primary():
            shard = self._resolve_shard(model, **hints)
            return shard or "default"

        # For replica reads, return the replica alias for this shard.
        shard = self._resolve_shard(model, **hints)
        if shard and shard in getattr(settings, "SHARD_MAP", {}):
            replica_alias = f"{shard}-replica"
            if replica_alias in settings.DATABASES:
                return replica_alias
        return shard or "default"

    # ── Write routing ────────────────────────────────────────────

    def db_for_write(self, model, **hints):
        """Route writes to the shard that owns this organization."""
        return self._resolve_shard(model, **hints) or "default"

    # ── Relation routing ─────────────────────────────────────────

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations only within the same shard.

        Two objects can be related if they belong to the same organization
        (and therefore the same shard). Cross-shard foreign keys are
        forbidden — they would break referential integrity.

        If we cannot determine the organization for either object, we
        allow the relation (conservative approach — let the database
        enforce constraints).
        """
        org1 = self._get_organization_id(obj1)
        org2 = self._get_organization_id(obj2)

        if org1 is not None and org2 is not None:
            return org1 == org2

        # If we can't determine org, allow it. PostgreSQL foreign key
        # constraints will catch true violations.
        return True

    # ── Migration routing ────────────────────────────────────────

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Run migrations on all shard databases.

        Migrations run on "default" AND all shard primaries. This
        ensures the schema is identical across shards.

        Replicas are skipped — they receive schema changes via
        streaming replication.
        """
        # Always allow on default.
        if db == "default":
            return True

        # Allow on shard primaries (shard-0, shard-1, etc.).
        if db in getattr(settings, "SHARD_MAP", {}):
            return True

        # Deny on replicas and unknown databases.
        return False

    # ── Internal helpers ─────────────────────────────────────────

    def _resolve_shard(self, model, **hints):
        """
        Determine which shard database alias to use.

        Resolution order:
        1. hints["organization_id"]
        2. hints["instance"].organization_id
        3. model field introspection (unlikely but supported)
        4. Fallback to None (caller uses "default")
        """
        org_id = None

        # Check hints first.
        if "organization_id" in hints:
            org_id = hints["organization_id"]
        elif "instance" in hints:
            org_id = self._get_organization_id(hints["instance"])

        if org_id is None:
            logger.debug(
                "Cannot determine shard for %s — falling back to default.",
                model.__name__ if model else "unknown",
            )
            return None

        # Use the consistent hash ring to map org_id → shard.
        try:
            shard = ring_manager.get_shard(org_id)
            return shard
        except Exception:
            logger.warning(
                "Ring lookup failed for organization_id=%s — falling back to default.",
                org_id,
            )
            return "default"

    @staticmethod
    def _get_organization_id(obj):
        """
        Extract organization_id from an object instance.

        Tries attribute access first, then falls back to checking
        if the object's model has the field.
        """
        if hasattr(obj, "organization_id"):
            return obj.organization_id
        try:
            return obj._meta.get_field("organization_id").value_from_object(obj)
        except Exception:
            return None
