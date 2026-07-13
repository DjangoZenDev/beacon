"""Beacon v0.16 — Migrate to Shards Command."""
from django.core.management.base import BaseCommand
from core.models import Page
from core.sharding.router import OrganizationShardRouter

class Command(BaseCommand):
    help = "Migrate pages to their target shards"
    def handle(self, *args, **options):
        router = OrganizationShardRouter(); count = 0
        for page in Page.objects.using("default").all():
            shard = router.db_for_write(Page, instance=page)
            if shard != "default":
                page.save(using=shard); count += 1
        self.stdout.write(self.style.SUCCESS(f"Migrated {count} pages"))
