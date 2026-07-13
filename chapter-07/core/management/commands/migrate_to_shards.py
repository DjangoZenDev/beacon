
"""Beacon v0.7 — migrate_to_shards. Carried forward from Ch6."""
import logging
from django.core.management.base import BaseCommand
from core.models import Page, PageLink
from core.sharding.backfill import backfill_orgs

logger = logging.getLogger("beacon.sharding")


class Command(BaseCommand):
    help = "Migrate data from default to shard cluster."

    def add_arguments(self, parser):
        parser.add_argument("--org-ids", nargs="+", type=int, help="Org IDs to migrate.")
        parser.add_argument("--all-orgs", action="store_true", help="Migrate all orgs.")
        parser.add_argument("--batch-size", type=int, default=500)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        if options["org_ids"]:
            org_ids = options["org_ids"]
        elif options["all_orgs"]:
            org_ids = list(Page.objects.values_list("organization_id", flat=True).distinct())
        else:
            self.stderr.write("Specify --org-ids or --all-orgs")
            return

        self.stdout.write(f"Migrating {len(org_ids)} organizations...")
        if options["dry_run"]:
            self.stdout.write("DRY RUN — no data will be modified.")
            self.stdout.write(f"Would migrate orgs: {org_ids}")
            return

        stats = backfill_orgs(org_ids, "default", "shard-0")
        self.stdout.write(self.style.SUCCESS(f"Done: {stats['pages_copied']} pages, {stats['links_copied']} links, {stats['errors']} errors"))
