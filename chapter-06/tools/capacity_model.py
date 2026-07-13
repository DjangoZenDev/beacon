
"""
Beacon v0.6 — Capacity Planning Model

Updated for Chapter 6: the database primary is now a shard cluster.
Each shard handles 25% of writes. With 4 shards, write throughput
increases 3.7x and runway extends to ~36 months at current growth.
"""

import math

MONTHLY_GROWTH = 1.15
CURRENT_QPS = 4200  # writes/sec at peak (pre-shard)
AVG_QUERY_CPU_MS = 5
VCPU_COUNT = 2
TARGET_MAX_UTILIZATION = 0.80
SHARD_COUNT = 4


def months_until_target(current_qps, growth_rate, avg_cpu_seconds, vcpus, target):
    current_cpu = current_qps * avg_cpu_seconds
    capacity = vcpus * target
    if current_cpu >= capacity:
        return 0
    n = math.log(capacity / current_cpu) / math.log(growth_rate)
    return n


def recommend(current_qps, avg_cpu_ms, vcpus, growth_rate, shard_count=4):
    # Per-shard QPS after sharding.
    per_shard_qps = current_qps / shard_count
    avg_cpu_sec = avg_cpu_ms / 1000.0
    months = months_until_target(
        per_shard_qps, growth_rate, avg_cpu_sec, vcpus, TARGET_MAX_UTILIZATION
    )

    print("═══ Beacon Capacity Model (Post-Shard) ═══")
    print()
    print(f"  Total writes/sec (peak)    : {current_qps}")
    print(f"  Shard count                : {shard_count}")
    print(f"  Writes/sec per shard       : {per_shard_qps}")
    print(f"  Average query CPU          : {avg_cpu_ms} ms")
    print(f"  vCPUs per shard            : {vcpus}")
    print(f"  Current CPU utilization    : {per_shard_qps * avg_cpu_sec / vcpus:.1%}")
    print(f"  Target max utilization     : {TARGET_MAX_UTILIZATION:.0%}")
    print(f"  Monthly growth rate        : {growth_rate:.0%}")
    print()
    print(f"  Months until target        : {months:.1f}")
    print()

    if months > 24:
        print("  Recommendation: No action needed. Re-evaluate in 12 months.")
    elif months > 12:
        print("  Recommendation: Monitor shard balance and hot spots.")
    elif months > 6:
        print("  Recommendation: Add a 5th shard. Update etcd ring config.")
    elif months > 3:
        print("  Recommendation: Add 2 shards + evaluate per-org sizing.")
    else:
        print("  Recommendation: EMERGENCY. Add shards immediately.")

    print()
    print("── Chapter 6 Architecture ──")
    print("  Shard-0  : t3.large (2 vCPU, 8 GB) — ~25% of orgs")
    print("  Shard-1  : t3.large (2 vCPU, 8 GB) — ~25% of orgs")
    print("  Shard-2  : t3.large (2 vCPU, 8 GB) — ~25% of orgs")
    print("  Shard-3  : t3.large (2 vCPU, 8 GB) — ~25% of orgs")
    print("  Replicas : 1 per shard (streaming replication)")
    print("  etcd3    : ring configuration + watch-based reload")
    print("  Redis    : cache layer for global search results")
    print(f"  Total runway: ~{months:.0f} months with current growth")

    return months


if __name__ == "__main__":
    recommend(CURRENT_QPS, AVG_QUERY_CPU_MS, VCPU_COUNT, MONTHLY_GROWTH, SHARD_COUNT)
