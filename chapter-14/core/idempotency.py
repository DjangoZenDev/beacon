"""Beacon v0.14 — Idempotency."""
from django.db import models, IntegrityError
class IdempotencyKey(models.Model):
    key = models.CharField(max_length=255, unique=True); created_at = models.DateTimeField(auto_now_add=True)
    result = models.JSONField(null=True, blank=True)
    def __str__(self): return self.key
def check_and_claim(key: str) -> tuple:
    try: return True, IdempotencyKey.objects.create(key=key).result
    except IntegrityError: existing = IdempotencyKey.objects.get(key=key); return False, existing.result
def store_result(key: str, result: dict): IdempotencyKey.objects.filter(key=key).update(result=result)
