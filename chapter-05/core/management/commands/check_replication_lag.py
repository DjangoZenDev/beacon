"""
Beacon v0.5 — check_replication_lag management command

Checks replication lag on the read replica by querying
pg_last_xact_replay_timestamp(). Reports the lag in seconds
and warns if it exceeds a configurable threshold.

Usage:
    python manage.py check_replication_lag

The PostgreSQL function pg_last_xact_replay_timestamp() returns the
timestamp of the last transaction replayed on the standby. Subtracting
it from NOW() gives the current replication lag.

A lag exceeding the warning threshold (default 5 seconds) indicates
one of:
- The primary is generating WAL faster than the replica can replay.
- The network between primary and replica is saturated.
- The replica is under-provisioned (CPU, disk I/O).
"""

from django.core.management.base import BaseCommand
from django.db import connections

# Logger for replication metrics.
import logging
logger = logging.getLogger("beacon.replication")


class Command(BaseCommand):
    help = "Check replication lag on the read replica."

    # Thresholds in seconds.
    LAG_WARN_SECONDS = 5    # Warn if replication lag exceeds this.
    LAG_CRIT_SECONDS = 30   # Critical if lag exceeds this.

    def handle(self, *args, **options):
        try:
            # Query the replica directly.
            with connections["replica"].cursor() as cursor:
                cursor.execute(
                    "SELECT "
                    "  NOW() - pg_last_xact_replay_timestamp() AS lag, "
                    "  pg_is_in_recovery(), "
                    "  pg_last_xact_replay_timestamp()"
                )
                row = cursor.fetchone()

            if row is None:
                self.stderr.write(self.style.ERROR(
                    "No result from replica query. Is the replica running?"
                ))
                return

            lag_interval, is_in_recovery, last_replay = row

            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("── Replication Status ──"))
            self.stdout.write("")

            if not is_in_recovery:
                self.stderr.write(self.style.ERROR(
                    "WARNING: Connected server is NOT in recovery mode. "
                    "This may be the primary, not the replica. Check your "
                    "DATABASES['replica'] HOST setting."
                ))
                return

            self.stdout.write(f"  In recovery       : Yes (this is a replica)")

            if last_replay is None:
                self.stdout.write(self.style.WARNING(
                    "  Last replay       : No transactions replayed yet. "
                    "The replica may have just started or replication may "
                    "not be configured."
                ))
                return

            # Convert PostgreSQL interval to seconds.
            lag_seconds = lag_interval.total_seconds()

            self.stdout.write(f"  Last replay at    : {last_replay}")
            self.stdout.write(f"  Replication lag   : {lag_seconds:.3f}s")

            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("── Assessment ──"))
            self.stdout.write("")

            if lag_seconds > self.LAG_CRIT_SECONDS:
                self.stdout.write(self.style.ERROR(
                    f"CRITICAL: Replication lag is {lag_seconds:.2f}s "
                    f"(threshold: {self.LAG_CRIT_SECONDS}s). "
                    f"The replica is significantly behind. Investigate "
                    f"primary WAL generation rate, network throughput, "
                    f"and replica disk I/O."
                ))
                logger.error(
                    "Replication lag CRITICAL: %.2fs (threshold: %ds)",
                    lag_seconds, self.LAG_CRIT_SECONDS,
                )
            elif lag_seconds > self.LAG_WARN_SECONDS:
                self.stdout.write(self.style.WARNING(
                    f"WARNING: Replication lag is {lag_seconds:.2f}s "
                    f"(threshold: {self.LAG_WARN_SECONDS}s)"
                ))
                logger.warning(
                    "Replication lag warning: %.2fs (threshold: %ds)",
                    lag_seconds, self.LAG_WARN_SECONDS,
                )
            else:
                self.stdout.write(self.style.SUCCESS(
                    f"Replication lag: {lag_seconds:.3f}s — healthy"
                ))

        except Exception as e:
            self.stderr.write(self.style.ERROR(
                f"Failed to check replication lag: {e}"
            ))
            logger.error("Failed to check replication lag: %s", e)
