# The 22 Principles That Remain
# Beacon v0.16 — Chapter 16: The Principles That Remain
#
# Extracted from the book "The Ascent" by Chapter.
# Maya taped this list to the wall on her last day.
# These apply at 100 users and at 100 million.

---

### Chapter 1: Start Simple
> **The simplest system that works is the best system you can build. Complexity is a tax you pay on every future change.**

Beacon began as two Django models, a single server, SQLite, and a dream.
Premature optimization is misinformed. You cannot optimize a system you
do not understand, and you cannot understand a system that hasn't been stressed.

**Chapter reference:** Chapter 1, "A Single Server and a Dream"

---

### Chapter 2: Measure Before You Scale
> **You do not know what to optimize until you measure what is slow. Guessing is the most expensive debugging technique.**

The first thousand users revealed Beacon's real bottlenecks: N+1 queries,
missing indexes, unoptimized ORM patterns. Django Debug Toolbar and
`EXPLAIN ANALYZE` fixed these in hours, not weeks.

**Chapter reference:** Chapter 2, "The First Thousand Users"

---

### Chapter 3: Cache By Access Pattern
> **Cache what is read frequently and written rarely. Invalidate what is written frequently and read rarely. Everything else is a tradeoff.**

Redis caching took page view latency from 200ms to 8ms. Cache-aside for
pages (read-heavy), write-through for sessions, write-behind for analytics.
Patterns, not products.

**Chapter reference:** Chapter 3, "Caching Everything That Moves"

---

### Chapter 4: Keep Background Work Out of the Request Path
> **The user's request is a promise. Do not break it because an email needs to be sent.**

Moving notification sends, search indexing, and analytics to Celery tasks
made every request faster and every failure isolated. The request-response
cycle is a synchronous contract. Everything else is asynchronous opportunity.

**Chapter reference:** Chapter 4, "The Monolith Groans"

---

### Chapter 5: Replicate Reads, Shard Writes
> **Reads scale horizontally with replicas. Writes scale horizontally with shards. They are different problems with different solutions.**

Read replicas solved the 10:1 read-to-write ratio for free. But replicas
introduced replication lag — and with it, the fundamental tradeoff between
consistency and availability.

**Chapter reference:** Chapter 5, "Read Replicas and the Split Brain"

---

### Chapter 6: Shard By Query Pattern, Not Data Distribution
> **The best shard key is the one that lets most queries hit exactly one shard.**

Beacon's `organization_id` shard key was right not because data was evenly
distributed (one org had 850K pages) but because 94% of queries were
scoped to a single organization.

**Chapter reference:** Chapter 6, "Sharding Beacon's Knowledge Graph"

---

### Chapter 7: Split On Seams, Not Nouns
> **A service boundary should reduce coordination cost more than it increases operational complexity.**

The import graph revealed three natural seams: search, notifications,
collaboration. The page service — the core CRUD — remained a monolith
because splitting it would increase coordination cost without reducing complexity.

**Chapter reference:** Chapter 7, "The Monolith Becomes a Service"

---

### Chapter 8: Events Are the Universal Interface
> **A message on a bus is more decoupled than a synchronous RPC. The tradeoff is eventual consistency — and it is almost always worth it.**

The outbox pattern ensured no database write was lost before it became a
message. Kafka gave the bus durability, ordering, and replay. Moving to
async events eliminated 150ms of coupling from every page save.

**Chapter reference:** Chapter 8, "Async Work and the Message Bus"

---

### Chapter 9: CRDTs Win By Avoiding Conflict
> **A data structure that cannot conflict is more reliable than an algorithm that resolves conflicts.**

Real-time collaboration was the hardest problem in the book. CRDTs solved
it by design: commutative, associative, idempotent merge operations that
converge without coordination.

**Chapter reference:** Chapter 9, "Collaboration at the Speed of Light"

---

### Chapter 10: Search Is a Database Design Problem
> **An inverted index is a database. Treat it like one.**

The progression from PostgreSQL `LIKE` to Elasticsearch was a progression
from row-oriented to term-oriented storage. The inverted index is a
different data structure for a different query pattern.

**Chapter reference:** Chapter 10, "Search Across a Billion Documents"

---

### Chapter 11: Fan-Out Is a Spectrum
> **Fan-out on write for the active. Fan-out on read for the inactive. Treat celebrity entities as a different class of problem.**

The hybrid feed approach turned an O(N × M) fan-out problem into
O(N + log M). Apache Flink made fan-out horizontally scalable.

**Chapter reference:** Chapter 11, "The Feed That Never Sleeps"

---

### Chapter 12: OLTP and OLAP Are Different Databases
> **Your application database is for serving users. Your analytical database is for understanding them.**

ClickHouse's columnar storage made analytical queries 100× faster than
PostgreSQL. Debezium + Kafka bridged the operational and analytical worlds.
CQRS — separate write and read models, connected by events.

**Chapter reference:** Chapter 12, "Data Lakes and the Analytical Sidecar"

---

### Chapter 13: Multi-Region Requires Multi-Everything
> **You cannot bolt global distribution onto a system designed for a single data center.**

Kubernetes across three continents. CockroachDB for geo-distributed SQL.
The CRDT engine running on every continent, converging without coordination.
A latency budget of 250ms that fit within the 300ms window allowed by physics.

**Chapter reference:** Chapter 13, "Going Multi-Region"

---

### Chapter 14: Observability Is a Discipline
> **You cannot fix what you cannot see. You cannot see what you do not measure.**

OpenTelemetry wired Django to Jaeger, Prometheus, and Loki with a single SDK.
The trace ID became the golden thread. MTTD dropped from 47 minutes to 4 minutes —
not because the system became simpler, but because it became visible.

**Chapter reference:** Chapter 14, "Observability When Things Go Dark"

---

### Chapter 15: Cost Is a Metric
> **Every architectural decision is a financial decision.**

Cost per request. FinOps showback. Terraform for infrastructure-as-code.
Pyroscope for continuous profiling. Beacon's monthly bill dropped from
$187K to $155K without degrading performance — because engineers
optimized what they could see.

**Chapter reference:** Chapter 15, "The Cost of Scale"

---

### Chapter 16: The Synthesis
> **Technology serves the idea. Never the reverse.**

The 22 principles are not a checklist. They are a framework — a way
of thinking about systems that has been tested across two years, 47
engineers, and a billion pages.

---

## The Five Meta-Principles

These five mental models transcend individual chapters:

**1. First Principles Thinking** — Trace the path. Measure every step.
The bottleneck will reveal itself.

**2. The Failure-First Mindset** — Assume every component will fail.
Design for that failure. Degrade gracefully, never lose data.

**3. The Ratio Mindset** — Engineering decisions are ratios. Cost per
request. Latency per operation. Errors per million. Optimize the ratio.

**4. The Migration Mindset** — Every architecture is temporary. Design
systems that are migratable — clean interfaces, versioned contracts,
dual-write paths.

**5. The Teaching Mindset** — The best engineers make themselves
unnecessary. Their legacy is systems and teams that continue long
after they leave.
