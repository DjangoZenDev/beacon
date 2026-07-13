
"""
Beacon v0.7 — Dual-Write Backfill

Carried forward from Chapter 6.
"""
import logging
logger = logging.getLogger("beacon.sharding")


def dual_write_save(instance, old_shard: str, new_shard: str):
    instance.save(using=old_shard)
    try:
        instance.save(using=new_shard)
        logger.info("Dual-write: %s pk=%s to %s and %s", instance.__class__.__name__, instance.pk, old_shard, new_shard)
    except Exception as exc:
        logger.error("Dual-write failed for %s pk=%s to %s: %s", instance.__class__.__name__, instance.pk, new_shard, exc)
    return instance
