"""Beacon v0.13 — Dual Write."""
import logging
logger = logging.getLogger("beacon.sharding")

def dual_write_save(instance, old_shard, new_shard):
    instance.save(using=old_shard)
    try: instance.save(using=new_shard); logger.info("Dual-write: %s pk=%s -> %s + %s", instance.__class__.__name__, instance.pk, old_shard, new_shard)
    except Exception as exc: logger.error("Dual-write failed: %s", exc)
    return instance
