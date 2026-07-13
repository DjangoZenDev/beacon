"""
Beacon v0.2 — Locust Load Test

This script simulates realistic user traffic against Beacon to measure
performance under load. It models three user behaviors:

1. Browsing:    View the page list (50% of traffic)
2. Reading:     View a specific page (35% of traffic)
3. Searching:   Search for a keyword (15% of traffic)

Run with:
    locust -f locustfile.py --host=http://localhost:8000

Then open http://localhost:8089 in a browser to start the test.

Chapter 2 uses this to:
- Establish baseline latency at 50 concurrent users
- Identify queries that degrade under load
- Confirm that select_related/prefetch_related fixes work
"""

import random

from locust import HttpUser, between, task


class BeaconUser(HttpUser):
    """
    A simulated Beacon user.

    Each user waits 1-5 seconds between actions (think time) and
    randomly picks an action weighted by the probabilities above.
    """

    wait_time = between(1, 5)

    def on_start(self):
        """
        Log in before running any tasks.

        In a real load test, you would create test user accounts in a
        setUp function. For now, we use Django's admin login.
        """
        self.client.post("/admin/login/", {
            "username": "loadtest",
            "password": "loadtest_password",
            "csrfmiddlewaretoken": self._get_csrf(),
        })

    def _get_csrf(self):
        """Extract CSRF token from the login page."""
        response = self.client.get("/admin/login/")
        # Simple extraction — production tests would use a proper parser.
        if "csrfmiddlewaretoken" in response.text:
            start = response.text.index("csrfmiddlewaretoken") + 41
            end = response.text.index('"', start)
            return response.text[start:end]
        return ""

    @task(50)
    def browse_pages(self):
        """
        View the page list — the most common action.

        Chapter 1: This query ran an N+1 count subquery.
        Chapter 2: select_related("author") + Count(distinct=True).
        """
        with self.client.get("/", name="page_list", catch_response=True) as r:
            if r.elapsed.total_seconds() > 0.5:
                r.failure(f"Page list took {r.elapsed.total_seconds():.2f}s")

    @task(35)
    def read_page(self):
        """
        View a specific page with its knowledge graph context.

        Chapter 1: 3 + N*2 queries (N = number of incoming + outgoing links).
        Chapter 2: Exactly 3 queries thanks to prefetch_related.
        """
        # Simulate reading a random page by slug.
        page_slugs = [
            "getting-started", "deployment-runbook", "api-design-standards",
            "on-call-rotation", "architecture-overview", "database-migration-guide",
            "code-review-checklist", "incident-postmortem-template",
        ]
        slug = random.choice(page_slugs)
        url = f"/page/{slug}/"

        with self.client.get(url, name="page_detail", catch_response=True) as r:
            if r.elapsed.total_seconds() > 0.5:
                r.failure(f"Page detail took {r.elapsed.total_seconds():.2f}s")
            if r.status_code == 404:
                # Page may not exist in test data — that's fine.
                r.success()

    @task(15)
    def search_pages(self):
        """
        Search for a keyword.

        Chapter 1: LIKE queries with sequential scan.
        Chapter 2: LIKE queries with PostgreSQL's better planner.
        Chapter 3: Redis caching for repeated searches.
        """
        keywords = ["deploy", "api", "database", "incident", "migration", "on-call"]
        query = random.choice(keywords)

        with self.client.get(
            f"/?q={query}", name="page_search", catch_response=True
        ) as r:
            if r.elapsed.total_seconds() > 1.0:
                r.failure(f"Search took {r.elapsed.total_seconds():.2f}s")
