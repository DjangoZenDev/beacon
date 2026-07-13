# SLO Definitions — Beacon v0.14
# Chapter 14: Observability
#
# SLOs are contracts with users. They define the acceptable
# degradation window. Error budgets are derived from SLOs
# and govern the feature-vs-reliability tradeoff.
#
# Principle: "SLOs are contracts, not targets."

## Service Level Objectives

### Availability
- **Target:** 99.9% uptime (monthly)
- **Error Budget:** 43 minutes of downtime per month
- **Measurement:** `(successful_requests / total_requests) >= 0.999`
- **Window:** 28-day rolling
- **Alert:** Burn rate > 5% of error budget consumed in 1 hour

### Latency
- **Target:** P95 < 500ms
- **Error Budget:** 0.1% of requests may exceed 500ms P95
- **Measurement:** `histogram_quantile(0.95, rate(beacon_request_duration_seconds_bucket[28d]))`
- **Window:** 28-day rolling
- **Alert:** P95 exceeds 500ms for > 5 minutes

### Freshness
- **Target:** Search index freshness < 5 seconds
- **Error Budget:** 0.1% of documents may be stale > 5s
- **Measurement:** `time() - max(beacon_search_index_last_updated)`
- **Window:** Real-time
- **Alert:** Max staleness > 30s for > 5 minutes

### Data Durability
- **Target:** 99.999% durability (no data loss)
- **Error Budget:** Zero tolerance for data loss
- **Measurement:** CockroachDB replication factor = 3 across regions
- **Alert:** Any replica set at risk (fewer than 3 replicas available)

## Error Budget Policy

When the 28-day error budget is exhausted for any SLO:
1. **Stop all feature deploys** immediately.
2. **Root cause analysis** within 24 hours.
3. **Reliability work only** until the error budget recovers (next 28-day window).
4. **Postmortem** published within 5 business days.

## Measurement Notes

- All SLOs are measured per region and globally.
- A region that exhausts its error budget blocks deploys only in that region.
- Global SLOs use the worst-performing region as the bound.
