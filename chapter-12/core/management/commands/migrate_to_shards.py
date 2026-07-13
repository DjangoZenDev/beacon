"Beacon v0.12 — Migrate to shards management command."
from django.core.management.base import BaseCommand
from core.models import Page

class Command(BaseCommand):
    help = "Migrate pages to their target shards based on organization_id"

    def handle(self, *args, **options):
        from core.sharding.router import OrganizationShardRouter
        router = OrganizationShardRouter()
        count = 0
        for page in Page.objects.using("default").all():
            shard = router.db_for_write(Page, instance=page)
            if shard != "default":
                page.save(using=shard)
                count += 1
        self.stdout.write(self.style.SUCCESS(f"Migrated {count} pages to shards"))
