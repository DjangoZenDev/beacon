# The Five Anti-Patterns That Kill Systems
# Beacon v0.16 — Chapter 16: The Principles That Remain
#
# Every anti-pattern below was observed in real systems.
# Each comes with symptoms, root cause, and remediation.

---

## Anti-Pattern 1: The Distributed Monolith

### Symptoms
- Every service depends on every other service.
- A change to notification-service requires deploying search-service.
- Latency is *higher* than the original monolith.
- Reliability is *lower* than the original monolith.
- The only thing that improved: the number of YAML files.

### Root Cause
Services were split by noun (UserService, PageService, NotificationService)
rather than by seam (bounded context in DDD terms). Each service shares
the same database. Each service calls the others synchronously.

### Remediation
- Services must own their data. No shared databases.
- If two services always deploy together, they are one service.
- Split only when coordination cost of keeping them together exceeds
  the operational cost of separating them.
- Use events (Kafka) for cross-service communication, not sync RPC.

### Beacon Example
In Chapter 7, Maya considered splitting the page CRUD into a separate
microservice but kept it as part of the monolith because the import
graph showed it was a single seam. She split only search, notifications,
and collaboration — three bounded contexts with clear APIs.

---

## Anti-Pattern 2: Resume-Driven Development

### Symptoms
- Kubernetes adopted for a 2-server system.
- Kafka adopted because "it's the industry standard" for 50 events/day.
- Go rewrite because "Go is faster" — ignoring that the bottleneck is
  the database, not the web framework.
- Team spends 3 months learning a new technology instead of 1 week
  optimizing the existing one.

### Root Cause
Engineers choose technologies for their resumes, not for the problem.
The question "what does this enable?" is replaced by "who else uses this?"

### Remediation
- Every technology decision must be justified by a specific, measured problem.
- "It's what Google uses" is not a justification.
- "Our P99 latency for search queries is 800ms and the database is running
  4,200 IOPS at saturation" is a justification.
- Solve the problems you have, not the problems you wish you had.

### Beacon Example
Maya resisted Kubernetes until Chapter 13, when Beacon needed multi-region
orchestration. Before that, Docker Compose was sufficient. She resisted
Kafka until Chapter 8, when synchronous gRPC calls were measurably
degrading page save latency by 150ms.

---

## Anti-Pattern 3: Alert Fatigue

### Symptoms
- On-call engineer receives 30 pages per night and acknowledges all
  without investigation.
- Dashboard has 47 red metrics that are always red.
- Team stops responding to "critical" alerts because everything is critical.
- Mean time to acknowledge (MTTA) increases week over week.

### Root Cause
Alerts fire on causes (high CPU, high memory) rather than symptoms
(user-facing errors). Thresholds are too tight. No alert hygiene —
alerts are added but never removed.

### Remediation
- **Every alert must require immediate human action.** If the correct
  response is "acknowledge and go back to sleep," the alert should not
  exist. Degrade it to a dashboard notification.
- Alert on symptoms, not causes. Users don't care about CPU — they
  care about errors and latency.
- Reduce alert volume until every page is investigated.
- If an alert fires 3 times and requires no action, degrade it.
- The signal-to-noise ratio of your alerting system is a measure of
  your engineering culture.

### Beacon Example
Chapter 14 redesigned Beacon's alerting: P95 latency > 500ms (user
symptom) replaced "CPU > 80%" (cause). Alert count dropped from 47
to 12. MTTA dropped from 15 minutes to 4 minutes.

---

## Anti-Pattern 4: Configuration Drift

### Symptoms
- Production database upgraded manually via SSH.
- Kubernetes node has a different kernel version because someone
  ran `apt-get upgrade` and forgot.
- Terraform state diverged from reality because of emergency fix
  in AWS console.
- "It works on my machine" — but not in staging or production.
- Snowflake servers: no two are identical.

### Root Cause
Manual changes to production bypass Git, code review, and CI/CD.
The reconciliation loop (Terraform plan, K8s controllers) is the
only mechanism that keeps infrastructure convergent — and it breaks
when manual changes are made outside the loop.

### Remediation
- Infrastructure as code, enforced by policy.
- No manual changes to production. None. Ever.
- Every change goes through Git → code review → CI/CD.
- Use `terraform plan` as a drift detector: run it on a schedule
  and alert if it shows changes.
- Immutable infrastructure: replace, don't patch.

### Beacon Example
Chapter 13 introduced Terraform for all infrastructure. Chapter 15
added AWS Budgets via Terraform. Every resource — GKE clusters,
CockroachDB nodes, Redis instances, CloudFront distributions —
is defined in `.tf` files under version control.

---

## Anti-Pattern 5: The Hero Engineer

### Symptoms
- One engineer knows how everything works.
- They are paged for every incident.
- They review every pull request.
- They cannot take a vacation.
- The system depends on knowledge that exists only in their head.
- Bus factor = 1.

### Root Cause
Knowledge is concentrated rather than distributed. The hero engineer
is rewarded for being indispensable — and the organization fails to
recognize that indispensability is a liability, not an asset.

### Remediation
- Runbooks, documentation, pair programming.
- Culture that values shared knowledge over individual heroism.
- Bus factor ≥ 3 for every subsystem.
- Every system has at least 2 people who can deploy, debug, and recover it.
- The hero engineer's job is to make themselves unnecessary.

### Beacon Example
Maya's departure from Beacon (Chapter 16) proved this principle: the
system ran smoothly without her. She had spent two years writing
runbooks, documenting decisions, mentoring engineers, and building
a platform that teams could use without her. The 22 principles taped
to the wall were her final act of making herself unnecessary.
