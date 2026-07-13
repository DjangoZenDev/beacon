"""
Beacon v0.5 — Read Replica Database Router

Chapter 5 introduces Django's multi-database support with a read-replica
router. The rule is simple:

- Reads (SELECT) → route to "replica"
- Writes (INSERT, UPDATE, DELETE) → route to "default" (primary)
- Migrations → run on "default" only
- Cross-database relations → allowed (both databases have the same schema)

Thread-local primary override:
When a request writes data and then reads it back (e.g., after saving a
page and redirecting to its detail view), the read should come from the
primary. The replica may not have received the write yet due to
replication lag. use_primary_for_request() sets a thread-local flag
that forces all reads to the primary for the remainder of that request.
"""

import threading

# Thread-local storage for per-request database routing decisions.
# Each request thread has its own copy of this flag. When a write
# occurs during a request, the flag is set to True, and subsequent
# reads within that same request are served from the primary.
_thread_locals = threading.local()


def use_primary_for_request():
    """
    Force all subsequent reads in this request to use the primary.

    Call this after performing a write that the user will immediately
    read back — for example, after saving a page and redirecting to
    its detail view. Without this, the read might hit the replica
    before the write has been streamed, causing "I saved my page but
    I still see the old version" bugs.

    The flag is thread-local, so it does not affect other requests.
    """
    _thread_locals.use_primary = True


def _should_use_primary():
    """Check whether this request should read from the primary."""
    return getattr(_thread_locals, "use_primary", False)


class ReadReplicaRouter:
    """
    Route reads to the replica, writes to the primary.

    The routing logic:
    - db_for_read: returns "replica" unless use_primary_for_request()
      was called, in which case it returns "default".
    - db_for_write: always returns "default".
    - allow_relation: returns True (both databases mirror each other).
    - allow_migrate: only "default" (migrations run on the primary and
      flow to the replica via streaming replication).

    What this router does NOT handle (and deliberately so):
    - Transaction-aware routing: if a transaction has written, reads
      within that transaction should use the primary. Django's default
      behavior does this — once you write in a transaction, Django
      pins that connection. The router is only consulted for the
      initial database selection.
    - Replication lag tolerance: the router does not know whether the
      replica is 10ms or 10s behind. It routes all reads to the
      replica by default. Views that need strong consistency (e.g.,
      "show me the page I just created") should call
      use_primary_for_request() or use the primary explicitly via
      .using("default").
    """

    def db_for_read(self, model, **hints):
        """
        Send reads to the replica.

        If use_primary_for_request() was called in this request
        thread, use the primary instead — the user just performed a
        write and reads should see the latest data.
        """
        if _should_use_primary():
            return "default"
        return "replica"

    def db_for_write(self, model, **hints):
        """All writes go to the primary."""
        return "default"

    def allow_relation(self, obj1, obj2, **hints):
        """
        Relations between objects are allowed.

        Since both databases contain identical data (the replica is a
        streaming copy of the primary), any two objects can be related
        regardless of which database they were read from.
        """
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Migrations only run on the primary.

        The replica receives schema changes via streaming replication
        of the DDL statements. Running migrations on the replica would
        cause conflicts and potentially break replication.
        """
        return db == "default"
