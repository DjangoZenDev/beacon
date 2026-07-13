"Beacon v0.12 — Idempotency Keys."
from django.db import models, IntegrityError

class IdempotencyKey(models.Model):
    key = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    result = models.JSONField(null=True, blank=True)

def check_and_claim(key):
    try:
        IdempotencyKey.objects.create(key=key)
        return True, None
    except IntegrityError:
        existing = IdempotencyKey.objects.get(key=key)
        return False, existing.result

def store_result(key, result):
    IdempotencyKey.objects.filter(key=key).update(result=result)
