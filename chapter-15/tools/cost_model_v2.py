
"""
Beacon v0.15 — Enhanced Capacity + Cost Model (v2)
Chapter 15: The Cost of Scale

Combines compute, database, cache, CDN, and storage costs
into a single model. Used for FinOps showback and capacity planning.

Principle: "Cost is a metric. Measure it."
  Every request has a dollar cost. Every architectural decision
  is a financial decision.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ResourceCost:
    """Monthly cost for a single resource category."""
    category: str
    monthly_cost: float
    unit: str  # e.g., "per node", "per GB", "per million requests"
    count: float
    unit_cost: float
    notes: str = ""


@dataclass
class CostModel:
    """Aggregated cost model for Beacon infrastructure."""

    resources: List[ResourceCost] = field(default_factory=list)
    total_monthly: float = 0.0
    cost_per_request: float = 0.0

    def add(self, category: str, count: float, unit_cost: float,
            unit: str = "units", notes: str = ""):
        monthly = count * unit_cost
        self.resources.append(ResourceCost(
            category=category, monthly_cost=monthly,
            unit=unit, count=count, unit_cost=unit_cost, notes=notes,
        ))
        self.total_monthly += monthly

    def compute_cost_per_request(self, requests_per_month: float):
        """Compute the blended cost per request."""
        if requests_per_month > 0:
            self.cost_per_request = self.total_monthly / requests_per_month
        return self.cost_per_request


def build_beacon_cost_model(
    regions: int = 3,
    k8s_nodes_per_region: int = 6,
    node_cost_per_month: float = 150.0,
    cockroachdb_nodes_per_region: int = 3,
    cockroachdb_node_cost: float = 400.0,
    redis_gb_per_region: float = 8.0,
    redis_cost_per_gb: float = 50.0,
    cdn_tb_per_month: float = 10.0,
    cdn_cost_per_gb: float = 0.02,
    storage_tb: float = 5.0,
    storage_cost_per_gb: float = 0.023,
    kafka_nodes_per_region: int = 3,
    kafka_node_cost: float = 200.0,
    requests_per_month: float = 5_000_000_000.0,  # ~5B/month
) -> CostModel:
    """
    Build a comprehensive cost model for multi-region Beacon.

    Args:
        regions: Number of regions (default 3).
        k8s_nodes_per_region: Kubernetes worker nodes.
        node_cost_per_month: Cost per K8s node (reserved instance).
        cockroachdb_nodes_per_region: CockroachDB nodes.
        cockroachdb_node_cost: Cost per CRDB node.
        redis_gb_per_region: Redis Memorystore GB per region.
        redis_cost_per_gb: Redis cost per GB-month.
        cdn_tb_per_month: CDN egress in TB.
        cdn_cost_per_gb: CloudFront cost per GB.
        storage_tb: S3/GCS storage in TB.
        storage_cost_per_gb: Storage cost per GB-month.
        kafka_nodes_per_region: Kafka broker nodes.
        kafka_node_cost: Cost per Kafka node.
        requests_per_month: Total monthly requests.

    Returns:
        CostModel with full breakdown.
    """
    model = CostModel()

    # Compute (Kubernetes nodes).
    total_nodes = regions * k8s_nodes_per_region
    model.add("Compute (K8s nodes)", total_nodes, node_cost_per_month,
              "per node", f"{k8s_nodes_per_region} nodes × {regions} regions")

    # Database (CockroachDB).
    total_crdb = regions * cockroachdb_nodes_per_region
    model.add("Database (CockroachDB)", total_crdb, cockroachdb_node_cost,
              "per node", f"{cockroachdb_nodes_per_region} nodes × {regions} regions")

    # Cache (Redis).
    total_redis_gb = regions * redis_gb_per_region
    model.add("Cache (Redis)", total_redis_gb, redis_cost_per_gb,
              "per GB", f"Standard HA, {redis_gb_per_region} GB × {regions} regions")

    # CDN (CloudFront).
    cdn_gb = cdn_tb_per_month * 1024
    model.add("CDN (CloudFront)", cdn_gb, cdn_cost_per_gb,
              "per GB", f"{cdn_tb_per_month} TB/month egress")

    # Storage (S3).
    storage_gb = storage_tb * 1024
    model.add("Storage (S3/GCS)", storage_gb, storage_cost_per_gb,
              "per GB", f"{storage_tb} TB stored")

    # Message bus (Kafka).
    total_kafka = regions * kafka_nodes_per_region
    model.add("Kafka", total_kafka, kafka_node_cost,
              "per node", f"{kafka_nodes_per_region} nodes × {regions} regions")

    # Cost per request.
    model.compute_cost_per_request(requests_per_month)

    return model


def print_cost_report(model: CostModel, requests_per_month: float):
    """Print a human-readable cost report."""
    print("=" * 65)
    print("  BEACON v0.15 — MONTHLY INFRASTRUCTURE COST REPORT")
    print("=" * 65)
    print(f"  {'Category':<28} {'Monthly':>10} {'Unit':>12}")
    print("-" * 65)
    for r in model.resources:
        print(f"  {r.category:<28} ${r.monthly_cost:>9,.2f} {r.unit:>11}")
    print("-" * 65)
    print(f"  {'TOTAL':<28} ${model.total_monthly:>9,.2f}")
    print(f"  {'Cost per 1M requests':<28} ${model.cost_per_request * 1_000_000:>9.4f}")
    print(f"  {'Requests/month':<28} {requests_per_month:>11,.0f}")
    print("=" * 65)

    # Recommendations.
    print("\n  Cost Optimization Opportunities:")
    if model.resources[0].monthly_cost > 3000:
        print("  • Consider reserved instances (1-year): ~30% savings on compute.")
    if model.resources[1].monthly_cost > 4000:
        print("  • Evaluate connection pooling to reduce DB nodes.")
    if model.resources[3].monthly_cost > 300:
        print("  • Enable CloudFront compression; review cache-hit ratio.")
    print()


if __name__ == "__main__":
    model = build_beacon_cost_model()
    print_cost_report(model, requests_per_month=5_000_000_000)
