"""Beacon v0.9 — migrate_to_shards (carried from Ch6)."""
import logging
from django.core.management.base import BaseCommand
from core.models import Page
from core.sharding.backfill import backfill_orgs
logger = logging.getLogger("beacon.sharding")

class Command(BaseCommand):
    help = "Migrate data to shard cluster."
    def add_arguments(self, parser):
        parser.add_argument("--org-ids", nargs="+", type=int)
        parser.add_argument("--all-orgs", action="store_true")
        parser.add_argument("--dry-run", action="store_true")
    def handle(self, *args, **options):
        if options["org_ids"]:
            org_ids = options["org_ids"]
        elif options["all_orgs"]:
            org_ids = list(Page.objects.values_list("organization_id", flat=True).distinct())
        else:
            self.stderr.write("Specify --org-ids or --all-orgs")
            return
        if options["dry_run"]:
            self.stdout.write(f"DRY RUN: would migrate {org_ids}")
            return
        stats = backfill_orgs(org_ids, "default", "shard-0")
        self.stdout.write(self.style.SUCCESS(f"Done: {stats['pages_copied']} pages, {stats['links_copied']} links, {stats['errors']} errors"))
