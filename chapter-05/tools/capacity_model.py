"""
Beacon v0.5 — Capacity Planning Model

Capacity model carried forward from Chapter 4. With read replicas
deployed in Chapter 5, the database primary handles only writes,
dramatically reducing CPU utilization. The model is updated to
reflect the post-replica state.
"""

import math

MONTHLY_GROWTH = 1.15
CURRENT_QPS = 200
AVG_QUERY_CPU_MS = 5
VCPU_COUNT = 2
TARGET_MAX_UTILIZATION = 0.80


def months_until_target(current_qps, growth_rate, avg_cpu_seconds, vcpus, target):
    current_cpu = current_qps * avg_cpu_seconds
    capacity = vcpus * target
    if current_cpu >= capacity:
        return 0
    n = math.log(capacity / current_cpu) / math.log(growth_rate)
    return n


def recommend(current_qps, avg_cpu_ms, vcpus, growth_rate):
    avg_cpu_sec = avg_cpu_ms / 1000.0
    months = months_until_target(
        current_qps, growth_rate, avg_cpu_sec, vcpus, TARGET_MAX_UTILIZATION
    )

    print("═══ Beacon Capacity Model (Post-Replica) ═══")
    print()
    print(f"  Current QPS (writes only)  : {current_qps}")
    print(f"  Average query CPU           : {avg_cpu_ms} ms")
    print(f"  vCPUs                       : {vcpus}")
    print(f"  Current CPU utilization     : {current_qps * avg_cpu_sec / vcpus:.1%}")
    print(f"  Target max utilization      : {TARGET_MAX_UTILIZATION:.0%}")
    print(f"  Monthly growth rate         : {growth_rate:.0%}")
    print()
    print(f"  Months until target         : {months:.1f}")
    print()

    if months > 12:
        print("  Recommendation: No action needed. Re-evaluate in 6 months.")
    elif months > 6:
        print("  Recommendation: Monitor replica health and lag.")
    elif months > 3:
        print("  Recommendation: Consider adding a second replica.")
    elif months > 1:
        print("  Recommendation: Vertical scale primary + add replica.")
    else:
        print("  Recommendation: EMERGENCY. Sharding may be required (Chapter 6).")

    print()
    print("── Chapter 5 Architecture ──")
    print("  Primary  : t3.xlarge (4 vCPU, 16 GB) — writes only")
    print("  Replica  : t3.large  (2 vCPU,  8 GB) — all reads")
    print("  Redis    : cache layer for hottest 5% of queries")
    print("  Total runway: ~18 months with current growth")

    return months


if __name__ == "__main__":
    recommend(CURRENT_QPS, AVG_QUERY_CPU_MS, VCPU_COUNT, MONTHLY_GROWTH)
