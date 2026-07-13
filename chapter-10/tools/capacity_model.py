"""Beacon v0.10 — Capacity model."""
import math
def recommend(current_qps=4200, avg_cpu_ms=5, vcpus=2, growth=1.15, shards=4):
    per = current_qps / shards; cpu = avg_cpu_ms/1000
    m = math.log(vcpus*0.8/(per*cpu))/math.log(growth) if per*cpu < vcpus*0.8 else 0
    print(f"=== Beacon v0.10 Capacity ===")
    print(f"  Writes/sec: {current_qps} total / {per} per shard")
    print(f"  Shards: {shards}"); print(f"  Runway: {m:.1f} months")
    print(f"  Search: Elasticsearch + BM25 (Ch10)")
    return m
if __name__ == "__main__": recommend()
