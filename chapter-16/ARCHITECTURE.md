# Beacon Architecture Decision Record
# Chapter 16: The Principles That Remain
#
# This document records every architectural decision made across
# all 16 chapters, organized by the Architecture Decision Framework
# (5 questions from the manuscript) and accompanied by a system
# diagram in ASCII art.
#
# Principle: "Every architecture is temporary. Design for migration."

## Architecture Decision Framework
#
# Before every major decision, Maya asked:
# 1. What problem are we solving? (one sentence)
# 2. What is the simplest solution that would work?
# 3. What are the alternatives? (at least two)
# 4. What breaks if this goes wrong?
# 5. How will we know it worked? (measurable)

---

## System Diagram (ASCII Art)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          GLOBAL TRAFFIC                                   │
│                    (Route 53 / Cloudflare DNS)                            │
└──────────────┬─────────────────────┬─────────────────────┬────────────────┘
               │                     │                     │
    ┌──────────▼──────────┐ ┌───────▼──────────┐ ┌───────▼──────────┐
    │   us-east (NA)      │ │  eu-west (EU)    │ │  ap-south (Asia) │
    │                     │ │                  │ │                  │
    │ ┌─────────────────┐ │ │ ┌──────────────┐ │ │ ┌──────────────┐ │
    │ │  Istio Gateway  │ │ │ │Istio Gateway │ │ │ │Istio Gateway │ │
    │ └────────┬────────┘ │ │ └──────┬───────┘ │ │ └──────┬───────┘ │
    │          │          │ │        │         │ │        │         │
    │ ┌────────▼────────┐ │ │ ┌──────▼───────┐ │ │ ┌──────▼───────┐ │
    │ │  Django (3x)    │ │ │ │ Django (3x)  │ │ │ │ Django (3x)  │ │
    │ │  Channels/ASGI  │ │ │ │ + Celery     │ │ │ │ + Celery     │ │
    │ └───┬───┬───┬─────┘ │ │ └──┬──┬──┬────┘ │ │ └──┬──┬──┬────┘ │
    │     │   │   │       │ │    │  │  │      │ │    │  │  │      │
    │ ┌───▼┐┌─▼─┐┌▼───┐  │ │ ┌──▼┐┌▼─┐┌▼──┐  │ │ ┌──▼┐┌▼─┐┌▼──┐  │
    │ │CRDB││Kfk││Reds│  │ │ │CR ││Kf││Rd │  │ │ │CR ││Kf││Rd │  │
    │ │3x  ││3x ││HA  │  │ │ │DB ││k ││is │  │ │ │DB ││k ││is │  │
    │ └────┘└───┘└────┘  │ │ └───┘└──┘└───┘  │ │ └───┘└──┘└───┘  │
    │                     │ │                  │ │                  │
    │ ┌─────────────────┐ │ │ ┌──────────────┐ │ │ ┌──────────────┐ │
    │ │Elasticsearch    │ │ │ │Elasticsearch │ │ │ │Elasticsearch │ │
    │ │ClickHouse       │ │ │ │ClickHouse    │ │ │ │ClickHouse    │ │
    │ └─────────────────┘ │ │ └──────────────┘ │ │ └──────────────┘ │
    └─────────────────────┘ └──────────────────┘ └──────────────────┘
               │                     │                     │
               └─────────────────────┼─────────────────────┘
                                     │
                         ┌───────────▼───────────┐
                         │   Cross-Region Kafka   │
                         │   (CRDT Sync Bridge)   │
                         └───────────────────────┘

           ┌──────────────────────────────────────────────┐
           │              GLOBAL DATA LAKE                 │
           │  S3 + Apache Iceberg + Trino (SQL query)     │
           │  CloudFront CDN (static/media edge cache)    │
           └──────────────────────────────────────────────┘
```

---

## Architecture Decision Records (ADRs)

### ADR-001: Django + PostgreSQL (Chapter 1)
- **Problem:** Need a web framework for a knowledge wiki.
- **Simplest solution:** Django with SQLite.
- **Alternatives:** Rails, Express, Laravel.
- **What breaks:** SQLite won't scale past 1 writer.
- **Success metric:** Serve 100 concurrent users at <200ms P95.
- **Status:** SUPERSEDED by ADR-005 (sharding).

### ADR-002: Redis Caching (Chapter 3)
- **Problem:** Page list view takes 200ms, mostly in database queries.
- **Simplest solution:** Django's per-view cache with memcached.
- **Alternatives:** Database query caching, CDN full-page caching.
- **What breaks:** Cache invalidation bugs cause stale data.
- **Success metric:** P95 latency < 50ms for cached page views.
- **Status:** ACTIVE. Extended by CDN (ADR-017).

### ADR-003: Celery for Async Tasks (Chapter 4)
- **Problem:** Email sends and search indexing block the request path.
- **Simplest solution:** `threading` module in-process.
- **Alternatives:** RQ, Dramatiq, manual polling.
- **What breaks:** In-process threads crash with the process.
- **Success metric:** 99.9% task delivery within 5 seconds.
- **Status:** ACTIVE. Extended by outbox pattern (ADR-008).

### ADR-004: Read Replicas (Chapter 5)
- **Problem:** 10:1 read-to-write ratio saturates the primary.
- **Simplest solution:** Django's `using()` with a read replica connection.
- **Alternatives:** Database proxy (PgBouncer), sharding.
- **What breaks:** Replication lag causes stale reads.
- **Success metric:** Primary CPU < 60% under peak load.
- **Status:** SUPERSEDED by CockroachDB (ADR-016).

### ADR-005: Sharding by organization_id (Chapter 6)
- **Problem:** 50M+ pages; single PostgreSQL can't hold them all.
- **Simplest solution:** PostgreSQL table partitioning.
- **Alternatives:** Vitess, Citus, application-level sharding.
- **What breaks:** Cross-org queries require scatter-gather.
- **Success metric:** 94% of queries hit exactly 1 shard.
- **Status:** ACTIVE. Coexists with CockroachDB.

### ADR-006: gRPC Page Service (Chapter 7)
- **Problem:** Search and notifications tightly coupled to the monolith.
- **Simplest solution:** REST API versioning.
- **Alternatives:** GraphQL, message queue, shared database.
- **What breaks:** Service boundaries increase latency by +50ms.
- **Success metric:** Services deploy independently; no shared DB.
- **Status:** ACTIVE. Extended by event-driven (ADR-011).

### ADR-007: Kafka for Events (Chapter 8)
- **Problem:** Synchronous gRPC calls couple services.
- **Simplest solution:** Redis pub/sub.
- **Alternatives:** RabbitMQ, NATS, SQS.
- **What breaks:** Message loss if no outbox pattern.
- **Success metric:** 150ms coupling eliminated per page save.
- **Status:** ACTIVE.

### ADR-008: Outbox Pattern (Chapter 8)
- **Problem:** Database writes and message publishes must be atomic.
- **Simplest solution:** Two-phase commit.
- **Alternatives:** Change data capture (Debezium), saga pattern.
- **What breaks:** Without outbox, messages can be lost on crash.
- **Success metric:** Zero message loss in chaos testing.
- **Status:** ACTIVE.

### ADR-009: CRDT for Collaboration (Chapter 9)
- **Problem:** Real-time co-editing without conflicts.
- **Simplest solution:** Operational Transform (OT).
- **Alternatives:** Last-write-wins, lock-based editing.
- **What breaks:** OT requires a central server for ordering.
- **Success metric:** CRDT convergence within 100ms of last edit.
- **Status:** ACTIVE. Extended globally (ADR-018).

### ADR-010: Elasticsearch for Search (Chapter 10)
- **Problem:** PostgreSQL `ILIKE` is O(N) for full-text search.
- **Simplest solution:** PostgreSQL full-text search (tsvector).
- **Alternatives:** Meilisearch, Typesense, Algolia.
- **What breaks:** ES cluster failure means no search.
- **Success metric:** P95 search latency < 200ms for 1B documents.
- **Status:** ACTIVE.

### ADR-011: Hybrid Feed (Chapter 11)
- **Problem:** Fan-out to 10M followers is O(N × M).
- **Simplest solution:** Fan-out on read only.
- **Alternatives:** Pure fan-out on write, pure fan-out on read.
- **What breaks:** Celebrity pages overwhelm write path.
- **Success metric:** Feed load time < 100ms for any user.
- **Status:** ACTIVE.

### ADR-012: ClickHouse + Iceberg (Chapter 12)
- **Problem:** OLAP queries on PostgreSQL take 78 seconds.
- **Simplest solution:** PostgreSQL materialized views.
- **Alternatives:** Snowflake, BigQuery, Redshift.
- **What breaks:** OLAP and OLTP share resources → both degrade.
- **Success metric:** Dashboard query < 500ms for 90-day window.
- **Status:** ACTIVE.

### ADR-013: Kubernetes (Chapter 13)
- **Problem:** Docker Compose can't orchestrate across 3 regions.
- **Simplest solution:** Docker Swarm.
- **Alternatives:** Nomad, ECS, raw VMs.
- **What breaks:** K8s complexity introduces new failure modes.
- **Success metric:** Zero-downtime rolling deploys across 3 regions.
- **Status:** ACTIVE.

### ADR-014: Istio Service Mesh (Chapter 13)
- **Problem:** Cross-region service discovery and routing.
- **Simplest solution:** DNS-based routing with nginx.
- **Alternatives:** Linkerd, Consul Connect, Cilium.
- **What breaks:** Sidecar proxy adds +2ms per hop.
- **Success metric:** Regional failover within 5 seconds.
- **Status:** ACTIVE.

### ADR-015: Terraform IaC (Chapter 13)
- **Problem:** Manual infrastructure changes cause drift.
- **Simplest solution:** Shell scripts with AWS CLI.
- **Alternatives:** Pulumi, CloudFormation, Ansible.
- **What breaks:** Terraform state divergence.
- **Success metric:** `terraform plan` shows zero drift.
- **Status:** ACTIVE.

### ADR-016: CockroachDB (Chapter 13)
- **Problem:** PostgreSQL can't survive region failure.
- **Simplest solution:** PostgreSQL with streaming replication.
- **Alternatives:** Spanner, YugabyteDB, Vitess.
- **What breaks:** Cross-region writes are 5× slower.
- **Success metric:** Survive loss of any 1 region with zero data loss.
- **Status:** ACTIVE.

### ADR-017: CloudFront CDN (Chapter 15)
- **Problem:** Global users experience 200ms+ latency for static assets.
- **Simplest solution:** Serve static assets from Gunicorn.
- **Alternatives:** Cloudflare, Fastly, self-hosted CDN.
- **What breaks:** CDN caching stale assets after deploy.
- **Success metric:** Static asset P95 latency < 20ms globally.
- **Status:** ACTIVE.

### ADR-018: Global CRDT via Kafka Bridge (Chapter 13)
- **Problem:** CRDT edits in one region must converge in all regions.
- **Simplest solution:** Global Redis cluster.
- **Alternatives:** CRDT-aware database, cross-region WebSocket mesh.
- **What breaks:** Network partition causes temporary divergence.
- **Success metric:** CRDT convergence < 2 seconds cross-region.
- **Status:** ACTIVE.

### ADR-019: OpenTelemetry (Chapter 14)
- **Problem:** Can't trace requests across 47 services.
- **Simplest solution:** Log-based correlation with request IDs.
- **Alternatives:** Datadog APM, New Relic, manual tracing.
- **Success metric:** MTTD < 5 minutes for production incidents.
- **Status:** ACTIVE.

### ADR-020: FinOps Showback (Chapter 15)
- **Problem:** Infrastructure cost invisible to engineering teams.
- **Simplest solution:** Monthly finance report PDF.
- **Alternatives:** Chargeback, cost-based routing.
- **What breaks:** Teams optimize for latency, ignore cost.
- **Success metric:** Monthly cost down 17% without perf degradation.
- **Status:** ACTIVE.

### ADR-021: Platform Team (Chapter 15)
- **Problem:** Infrastructure sprawl from 6 independent teams.
- **Simplest solution:** Infrastructure ticket queue.
- **Alternatives:** Embedded SRE per team, full self-service.
- **What breaks:** Platform team becomes a bottleneck.
- **Success metric:** Infrastructure request → provisioned < 4 hours.
- **Status:** ACTIVE.

### ADR-022: Architecture Decision Framework (Chapter 16)
- **Problem:** Ad-hoc decisions without consistent evaluation.
- **Simplest solution:** "Use what Google uses."
- **Alternatives:** RFC process, design review board.
- **What breaks:** Decisions without recorded rationale are unrevisable.
- **Success metric:** Every ADR answers all 5 framework questions.
- **Status:** ACTIVE.
