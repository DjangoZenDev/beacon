"""Beacon v0.13 — Capacity model with multi-region awareness."""
import math
def recommend(current_qps=4200, avg_cpu_ms=5, vcpus=2, growth=1.15, shards=4, regions=3):
    per_region = current_qps / regions; per_shard = per_region / shards
    cpu = avg_cpu_ms/1000
    m = math.log(vcpus*0.8/(per_shard*cpu))/math.log(growth) if per_shard*cpu < vcpus*0.8 else 0
    print(f"=== Beacon v0.13 Multi-Region Capacity ===")
    print(f"  Total QPS: {current_qps} across {regions} regions")
    print(f"  Per Region: {per_region:.0f} qps / {per_shard:.0f} per shard")
    print(f"  Regions: {regions} | Shards per region: {shards}")
    print(f"  Runway: {m:.1f} months at {growth*100:.0f}% MoM growth")
    return m
if __name__ == "__main__": recommend()
