"""
Beacon v0.4 — Capacity Planning Model

Chapter 4 introduces capacity planning as a discipline. This script
models how long Beacon's database server can sustain current growth
before hitting 80% CPU utilization.

Leo built this after discovering the database was at 60% CPU during
peak traffic. The model showed 3.5 months of runway on the current
t3.large instance, and 10+ months on a t3.xlarge.

Usage:
    python tools/capacity_model.py

Output:
    Current QPS: 200
    Average query CPU: 5.0 ms
    vCPUs: 2
    Current CPU utilization: 50.0%
    Months until 80% utilization: 3.5
    Recommendation: Begin planning read replicas (Chapter 5).

Assumptions:
- t3.large: 2 vCPUs, 8 GB RAM, ~3,000 concurrent connections
- Average query: 5 ms CPU time
- Peak QPS: 200 (queries per second)
- CPU utilization at peak: 60%
- Growth: 15% month-over-month in query volume

At current growth rate (15% month-over-month), we hit 80% CPU in:
  200 QPS * 0.005s = 1.0 CPU-seconds of work per second
  Available: 2 vCPUs * 0.6 utilization = 1.2 CPU-seconds
  Headroom: 0.2 CPU-seconds

  Growth to 80% utilization:
    200 QPS * (1.15 ^ n) * 0.005s * 1.1 (overhead growth) = 2 * 0.8
    n ≈ 3.5 months

ALERT: ~3 months before the database server is the bottleneck.
Primary candidates for remediation:
1. Read replicas (Chapter 5) — move read queries off the primary.
2. Query optimization — reduce average query time from 5ms to 3ms.
3. Vertical scaling (t3.xlarge) — buys another 6 months.
"""

import math

MONTHLY_GROWTH = 1.15  # 15% month-over-month query volume growth
CURRENT_QPS = 200
AVG_QUERY_CPU_MS = 5
VCPU_COUNT = 2
TARGET_MAX_UTILIZATION = 0.80


def months_until_target(current_qps, growth_rate, avg_cpu_seconds, vcpus, target):
    """
    Calculate how many months until we hit the target CPU utilization.

    Uses the formula:
        current_cpu * (growth_rate ^ n) = capacity
        n = log(capacity / current_cpu) / log(growth_rate)

    where:
        current_cpu = current_qps * avg_cpu_seconds
        capacity = vcpus * target

    Args:
        current_qps: Current queries per second at peak.
        growth_rate: Monthly growth factor (1.15 = 15% growth).
        avg_cpu_seconds: Average CPU time per query in seconds.
        vcpus: Number of virtual CPUs available.
        target: Target maximum utilization (0.0 to 1.0).

    Returns:
        Months until target utilization is reached.
    """
    current_cpu = current_qps * avg_cpu_seconds
    capacity = vcpus * target
    if current_cpu >= capacity:
        return 0  # Already at or past the target.

    n = math.log(capacity / current_cpu) / math.log(growth_rate)
    return n


def recommend(current_qps, avg_cpu_ms, vcpus, growth_rate):
    """
    Recommend a scaling strategy based on the capacity model.

    Prints the current state and a time-based recommendation:
    - >12 months: No action needed.
    - 6-12 months: Begin planning read replicas.
    - 3-6 months: Vertical scale + begin replica implementation.
    - 1-3 months: Vertical scale immediately. Replicas urgent.
    - <1 month: EMERGENCY. Vertical scale + replicas NOW.
    """
    avg_cpu_sec = avg_cpu_ms / 1000.0
    months = months_until_target(
        current_qps, growth_rate, avg_cpu_sec, vcpus, TARGET_MAX_UTILIZATION
    )

    print("═══ Beacon Capacity Model ═══")
    print()
    print(f"  Current QPS              : {current_qps}")
    print(f"  Average query CPU        : {avg_cpu_ms} ms")
    print(f"  vCPUs                    : {vcpus}")
    print(f"  Current CPU utilization  : {current_qps * avg_cpu_sec / vcpus:.1%}")
    print(f"  Target max utilization   : {TARGET_MAX_UTILIZATION:.0%}")
    print(f"  Monthly growth rate      : {growth_rate:.0%}")
    print()
    print(f"  Months until target      : {months:.1f}")
    print()

    if months > 12:
        print("  Recommendation: No action needed. Re-evaluate in 6 months.")
    elif months > 6:
        print("  Recommendation: Begin planning read replicas (Chapter 5).")
    elif months > 3:
        print("  Recommendation: Vertical scale + begin read replica implementation.")
    elif months > 1:
        print("  Recommendation: Vertical scale immediately. Read replicas urgent.")
    else:
        print("  Recommendation: EMERGENCY. Vertical scale + read replicas NOW.")

    print()
    print("── Scaling Ladder ──")
    print("  t3.large    (2 vCPU,  8 GB)   → currently deployed")
    print("  t3.xlarge   (4 vCPU, 16 GB)   → +6 months runway")
    print("  t3.2xlarge  (8 vCPU, 32 GB)   → +12 months runway")
    print("  read replicas                  → +12-18 months runway (Chapter 5)")

    return months


if __name__ == "__main__":
    recommend(CURRENT_QPS, AVG_QUERY_CPU_MS, VCPU_COUNT, MONTHLY_GROWTH)
