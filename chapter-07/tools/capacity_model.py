
"""Beacon v0.7 — Capacity Planning (Post-Service Split)."""
import math
MONTHLY_GROWTH = 1.15
CURRENT_QPS = 4200
AVG_QUERY_CPU_MS = 5
VCPU_COUNT = 2
TARGET_MAX_UTILIZATION = 0.80
SHARD_COUNT = 4


def months_until_target(cqps, gr, cpu_sec, vcpus, target):
    cc = cqps * cpu_sec
    cap = vcpus * target
    if cc >= cap:
        return 0
    return math.log(cap / cc) / math.log(gr)


def recommend(current_qps, avg_cpu_ms, vcpus, growth_rate, shard_count=4):
    per_shard = current_qps / shard_count
    cpu_sec = avg_cpu_ms / 1000.0
    months = months_until_target(per_shard, growth_rate, cpu_sec, vcpus, TARGET_MAX_UTILIZATION)
    print("=== Beacon Capacity Model (Post-Service Split) ===")
    print(f"  Writes/sec (total): {current_qps}")
    print(f"  Per shard: {per_shard}")
    print(f"  Months until next scale: {months:.1f}")
    print("  Architecture: 4 shards + 4 gRPC services + Kafka + ES")
    print(f"  Runway: ~{months:.0f} months")
    return months


if __name__ == "__main__":
    recommend(CURRENT_QPS, AVG_QUERY_CPU_MS, VCPU_COUNT, MONTHLY_GROWTH, SHARD_COUNT)
