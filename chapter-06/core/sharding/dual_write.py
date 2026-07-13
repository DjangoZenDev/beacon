"""
Beacon v0.6 — Dual-Write Backfill

When resharding (adding or removing a shard), data must be migrated
from old shards to new shards without downtime. The dual-write pattern
is the only safe approach for live systems:

1. Write to BOTH the old shard and the new shard.
2. Backfill existing data from old shard to new shard in batches.
3. Verify data integrity (checksum comparison).
4. Cut over reads to the new shard.
5. Stop writing to the old shard.

This module provides the dual_write_save() function that writes a model
instance to multiple shards within a single logical operation.

Chapter 6, Principle 9: "Dual-write backfill is the only safe
resharding pattern."
"""

import logging

from django.db import transaction

logger = logging.getLogger("beacon.sharding")


def dual_write_save(instance, old_shard: str, new_shard: str):
    """
    Save an instance to both the old and new shard.

    Used during resharding when an organization is being moved from
    one shard to another. The instance is saved to both databases
    so that reads can be served from either shard during the
    transition period.

    Both saves happen atomically at the application level (not a
    distributed transaction — that's impossible across PostgreSQL
    instances). This means there is a brief window where one shard
    has the write and the other doesn't. The backfill process handles
    reconciliation for this edge case.

    Args:
        instance: A Django model instance to save.
        old_shard: The database alias of the old shard.
        new_shard: The database alias of the new shard.

    Returns:
        The saved instance.
    """
    # Save to old shard first (the one currently serving reads).
    instance.save(using=old_shard)

    # Save to new shard.
    try:
        instance.save(using=new_shard)
        logger.info(
            "Dual-write: %s pk=%s to %s and %s",
            instance.__class__.__name__,
            instance.pk,
            old_shard,
            new_shard,
        )
    except Exception as exc:
        logger.error(
            "Dual-write failed for %s pk=%s to %s: %s",
            instance.__class__.__name__,
            instance.pk,
            new_shard,
            exc,
        )
        # The old shard has the write. The backfill will catch up.
        # Do not re-raise — let the request succeed on the old shard.

    return instance
