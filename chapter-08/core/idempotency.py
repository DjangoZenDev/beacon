
"""
Beacon v0.8 — Idempotency Keys

Makes async task processing idempotent. Each key is unique per operation.
If the key already exists, the task was already processed — skip it.

Chapter 8, Principle 3: "Make every task idempotent."
"""

from django.db import models, IntegrityError


class IdempotencyKey(models.Model):
    key = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    result = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.key


def check_and_claim(key: str) -> tuple[bool, dict | None]:
    """Return (is_new, previous_result). If is_new, the caller should proceed."""
    try:
        ik = IdempotencyKey.objects.create(key=key)
        return True, None
    except IntegrityError:
        existing = IdempotencyKey.objects.get(key=key)
        return False, existing.result


def store_result(key: str, result: dict):
    """Store the result of processing for a claimed idempotency key."""
    IdempotencyKey.objects.filter(key=key).update(result=result)
