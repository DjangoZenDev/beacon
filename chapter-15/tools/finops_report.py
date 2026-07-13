
#!/usr/bin/env python3
"""
Beacon v0.15 — FinOps Monthly Cost Report Generator
Chapter 15: The Cost of Scale

Generates a monthly cost breakdown by service from AWS/GCP billing data.
Used for FinOps showback to every engineering team.

Principle: "Visibility drives optimization."
  Show every team their infrastructure costs. Don't punish — inform.

Usage:
    python tools/finops_report.py --month 2025-09 --output report.json
"""

import argparse
import json
import os
from datetime import datetime
from typing import Dict, List


SERVICE_CATEGORIES = {
    "ec2": "Compute (EC2/GKE)",
    "elasticache": "Cache (Redis)",
    "rds": "Database",
    "s3": "Storage (S3/GCS)",
    "cloudfront": "CDN",
    "kafka": "Message Bus",
    "elasticsearch": "Search",
    "kms": "Security",
    "data_transfer": "Network",
}

TEAM_OWNERSHIP = {
    "search-service": "Search Team",
    "feed-service": "Feed Team",
    "collab-service": "Collaboration Team",
    "page-service": "Core Platform",
    "notify-service": "Core Platform",
    "infrastructure": "Platform Team",
}


class FinOpsReport:
    """Generates cost allocation reports for FinOps showback."""

    def __init__(self, month: str):
        self.month = month
        self.by_service: Dict[str, float] = {}
        self.by_team: Dict[str, float] = {}
        self.total = 0.0

    def add_cost(self, service: str, cost: float, team: str = ""):
        self.by_service[service] = self.by_service.get(service, 0) + cost
        team = team or self._infer_team(service)
        self.by_team[team] = self.by_team.get(team, 0) + cost
        self.total += cost

    def _infer_team(self, service: str) -> str:
        for prefix, team in TEAM_OWNERSHIP.items():
            if service.startswith(prefix):
                return team
        return "Platform Team"

    def generate(self) -> dict:
        """Generate the report as a dict."""
        return {
            "report_month": self.month,
            "generated_at": datetime.utcnow().isoformat(),
            "total_monthly_cost": round(self.total, 2),
            "by_category": self._categorize(),
            "by_service": {
                k: round(v, 2) for k, v in
                sorted(self.by_service.items(), key=lambda x: -x[1])
            },
            "by_team": {
                k: round(v, 2) for k, v in
                sorted(self.by_team.items(), key=lambda x: -x[1])
            },
            "cost_per_request": self._cost_per_request(),
        }

    def _categorize(self) -> Dict[str, float]:
        result: Dict[str, float] = {}
        for svc, cost in self.by_service.items():
            cat = "Other"
            for prefix, category in SERVICE_CATEGORIES.items():
                if svc.lower().startswith(prefix):
                    cat = category
                    break
            result[cat] = result.get(cat, 0) + cost
        return {k: round(v, 2) for k, v in sorted(result.items(), key=lambda x: -x[1])}

    def _cost_per_request(self) -> float:
        """Estimate cost per million requests from Prometheus data."""
        from core.metrics import request_duration_seconds
        total_requests = 5_000_000_000  # Default: 5B/month
        return round(self.total / total_requests * 1_000_000, 6)

    def print_report(self):
        """Print the report to stdout."""
        r = self.generate()
        print("=" * 60)
        print(f"  BEACON FINOPS REPORT — {r['report_month']}")
        print("=" * 60)
        print(f"\n  Total Monthly Cost: ${r['total_monthly_cost']:,.2f}")
        print(f"  Cost per 1M requests: ${r['cost_per_request']:.4f}")

        print(f"\n  ── By Category ──")
        for cat, cost in r["by_category"].items():
            pct = (cost / r["total_monthly_cost"]) * 100 if r["total_monthly_cost"] else 0
            print(f"  {cat:<30} ${cost:>10,.2f}  ({pct:>5.1f}%)")

        print(f"\n  ── By Team ──")
        for team, cost in r["by_team"].items():
            pct = (cost / r["total_monthly_cost"]) * 100 if r["total_monthly_cost"] else 0
            print(f"  {team:<30} ${cost:>10,.2f}  ({pct:>5.1f}%)")
        print()


def load_sample_data() -> FinOpsReport:
    """Load sample cost data for demonstration."""
    report = FinOpsReport(month="2025-09")

    # Sample costs mirror manuscript Chapter 15 numbers.
    report.add_cost("ec2-us-east", 8000, "Core Platform")
    report.add_cost("ec2-eu-west", 6500, "Core Platform")
    report.add_cost("ec2-ap-south", 5500, "Core Platform")
    report.add_cost("elasticache-us-east", 2400, "Core Platform")
    report.add_cost("elasticache-eu-west", 2000, "Core Platform")
    report.add_cost("rds-us-east", 12000, "Core Platform")
    report.add_cost("rds-eu-west", 9000, "Core Platform")
    report.add_cost("s3-storage", 3500, "Platform Team")
    report.add_cost("cloudfront-cdn", 2200, "Platform Team")
    report.add_cost("kafka-us-east", 1800, "Platform Team")
    report.add_cost("kafka-eu-west", 1500, "Platform Team")
    report.add_cost("elasticsearch-search", 15000, "Search Team")
    report.add_cost("kafka-feed", 2500, "Feed Team")
    report.add_cost("redis-crdt", 8400, "Collaboration Team")
    report.add_cost("elasticsearch-search-eu", 8000, "Search Team")
    report.add_cost("redis-feed-cache", 3200, "Feed Team")
    report.add_cost("data_transfer", 4500, "Platform Team")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Beacon FinOps Monthly Report")
    parser.add_argument("--month", default="2025-09", help="Report month (YYYY-MM)")
    parser.add_argument("--output", help="Output JSON file path")
    parser.add_argument("--sample", action="store_true", help="Use sample data")
    args = parser.parse_args()

    if args.sample:
        report = load_sample_data()
    else:
        report = FinOpsReport(month=args.month)
        # In production, load from AWS Cost Explorer / GCP Billing API.

    report.print_report()

    if args.output:
        with open(args.output, "w") as f:
            json.dump(report.generate(), f, indent=2)
        print(f"Report saved to {args.output}")
