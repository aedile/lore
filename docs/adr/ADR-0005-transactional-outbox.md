# ADR-0005: Transactional Outbox for Cross-Context Events

| Field | Value |
|-------|-------|
| **Status** | ACCEPTED |
| **Date** | 2026-04-29 |
| **Phase** | Phase 00 (synthesis pre-Phase 1) |
| **Originating findings** | R2 F-101 (idempotency contract per stage), R2 F-102 (transactional outbox), R2 F-103 (idempotent consumers), R2 F-107 (audit emission durability) |

---

## Context

The system is event-driven across bounded contexts: Identity Resolution emits
`match-decisions`; Canonical Eligibility emits `lifecycle-events`; every
context emits `audit-events`. Cross-context events are published via
Pub/Sub with at-least-once delivery semantics.

Without explicit discipline, three failure modes accumulate:

1. **Event-vs-state divergence**: a state change is committed to the database,
   but the corresponding Pub/Sub publish fails (transient network error,
   broker outage). Downstream consumers never see the event; their derived
   state diverges from the canonical state permanently.

2. **Phantom events**: a Pub/Sub publish succeeds but the database commit
   fails (unique constraint violation, deadlock retry exhausted). Downstream
   consumers see an event for a state that was never persisted.

3. **Duplicate processing**: Pub/Sub at-least-once delivery means consumers
   may see the same event multiple times. Without idempotent consumers,
   downstream effects (audit chain entries, canonical state transitions,
   match decisions) duplicate.

The standard answer to (1) and (2) is the **transactional outbox pattern**.
The standard answer to (3) is **idempotent consumers** keyed by a stable
event identifier.

## Decision

### 1. Outbox table per context

Each bounded context with state-changing operations has an `outbox` table
co-resident with its primary database. Schema:

```sql
CREATE TABLE outbox (
    event_id           UUID         PRIMARY KEY,
    topic              TEXT         NOT NULL,
    ordering_key       TEXT,                      -- per Pub/Sub ordering key model
    payload            JSONB        NOT NULL,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT now(),
    published_at       TIMESTAMPTZ,
    retry_count        INTEGER      NOT NULL DEFAULT 0,
    last_attempt_at    TIMESTAMPTZ,
    last_error         TEXT
);

CREATE INDEX idx_outbox_unpublished
    ON outbox(created_at) WHERE published_at IS NULL;
```

### 2. Producer pattern (atomic write)

Every state-changing operation that emits an event:

```python
async with database.transaction() as tx:
    # 1. State change
    await tx.execute(state_change_sql, state_change_params)

    # 2. Outbox insert in the SAME transaction
    event = build_event(state_change_result)
    await tx.execute(
        "INSERT INTO outbox (event_id, topic, ordering_key, payload) "
        "VALUES ($1, $2, $3, $4)",
        event.event_id, event.topic, event.ordering_key, event.payload,
    )

    # 3. Commit (atomic — either both rows persist or neither do)
```

State change and outbox row commit atomically. If the transaction rolls back,
neither persists.

### 3. Publisher service

A small Cloud Run service (the **outbox-publisher**, one per context, or one
shared instance polling all contexts' outbox tables) reads unpublished outbox
rows and publishes to Pub/Sub:

```
Loop:
    rows = SELECT * FROM outbox WHERE published_at IS NULL
                                  ORDER BY created_at LIMIT N
    For each row:
        publish to row.topic with row.payload, row.event_id, row.ordering_key
        on success: UPDATE outbox SET published_at = now() WHERE event_id = row.event_id
        on failure: increment retry_count, set last_attempt_at, set last_error;
                    re-loop with backoff
```

Publisher characteristics:
- **Idempotent on publish**: Pub/Sub's `event_id` deduplication (Pub/Sub
  message attribute) ensures duplicate publishes don't reach consumers twice.
- **Bounded backlog**: outbox row count alerted at threshold (D-061).
- **Crash-safe**: a publisher crash mid-loop is recovered by the next
  iteration; the outbox row stays unpublished until success.

Trade-off: this introduces ~1 second of publish lag (publisher polling +
processing). Acceptable for asynchronous flows; not acceptable for the
Verification API hot path (which is request/response, not event-driven).

### 4. Consumer idempotency

Every consumer of a Pub/Sub topic maintains a **processed_events** record
keyed by `event_id`:

```sql
CREATE TABLE processed_events (
    event_id           UUID         PRIMARY KEY,
    topic              TEXT         NOT NULL,
    processed_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX idx_processed_events_topic_time
    ON processed_events(topic, processed_at);
```

Consumer processing:

```python
async with database.transaction() as tx:
    # 1. Check idempotency
    row = await tx.fetchone(
        "SELECT 1 FROM processed_events WHERE event_id = $1",
        message.event_id,
    )
    if row:
        # Already processed; ack and return
        return

    # 2. Process the event (state changes, downstream outbox writes)
    await process(message)

    # 3. Mark as processed
    await tx.execute(
        "INSERT INTO processed_events (event_id, topic) VALUES ($1, $2)",
        message.event_id, message.topic,
    )

    # 4. Commit
```

If processing produces downstream events, those use this context's outbox
(per producer pattern above) — chaining the guarantees.

`processed_events` is pruned on a schedule (e.g., events older than 30 days
removed) to bound table size; the assumption is Pub/Sub retention plus
processing latency is bounded well below the prune horizon.

### 5. Audit emission

Audit events use the same outbox mechanism. Per R2 F-107: audit emission
must not be a separate failure mode from the operation it records. The
outbox row for the audit event is committed in the same transaction as the
state change, guaranteeing audit durability without coupling availability to
Pub/Sub.

### 6. Pub/Sub ordering keys

Ordering matters for some streams (per R2 F-106 — audit events for the same
target token must be processed in order). Pub/Sub's ordering key feature is
used:

- `audit-events` topic: `ordering_key = target_token` (orders audit events
  per subject).
- `match-decisions` topic: `ordering_key = candidate_record_ref`.
- `lifecycle-events` topic: `ordering_key = member_id`.
- `staging-records` topic: `ordering_key = source_file_id`.

## Consequences

### Positive

- **No event-vs-state divergence**: outbox row and state change are atomic.
- **No phantom events**: nothing publishes that didn't commit.
- **Idempotent consumers**: duplicate delivery is absorbed.
- **Audit durability**: audit emission tied to the operation it records.
- **Replay-safe**: outbox + processed_events together support replay
  scenarios (BR-606) — re-running a stage doesn't double-process.

### Negative

- **Two extra tables per context**: outbox + processed_events.
- **Publisher service per context** (or shared) adds operational surface.
- **Publish latency**: ~1 second for the publisher to pick up new rows.
  Not on the Verification API hot path; acceptable for event-driven flows.
- **Outbox cleanup**: published rows must be archived or deleted to bound
  table size; cleanup process is operational overhead.

### Mitigations

- Publisher service is a small, well-bounded component; can be the same
  process as the producer service in low-volume contexts.
- Outbox cleanup is a scheduled DAG (Composer); published rows older than
  30 days move to a `outbox_archive` partition or are deleted (per
  retention policy).
- Monitoring on outbox backlog (count of unpublished rows) provides early
  warning of publisher issues.

## Alternatives considered

1. **Direct Pub/Sub publish from the producer transaction**: rejected.
   Pub/Sub publish is not transactional with the database; failures cause
   event-vs-state divergence.
2. **Two-phase commit (XA)**: rejected. Pub/Sub does not support 2PC;
   distributed transactions are operationally fragile.
3. **Eventual consistency with reconciliation**: rejected for primary
   path. Reconciliation can detect drift but cannot prevent it; for
   audit-bearing systems, prevention is required.
4. **Change Data Capture (CDC) on the database**: alternative pattern where
   a CDC reader (Datastream-like) emits events from the database WAL.
   Rejected for v1: adds operational complexity (CDC reader); ties the
   event schema to the database schema (coupling); harder to control
   message format and ordering. May revisit if outbox volume becomes
   problematic.

## References

- Originating findings: R2 F-101, R2 F-102, R2 F-103, R2 F-106, R2 F-107
- ADR-0001 (Harness Foundation)
- BR-501..505 (Audit), BR-606 (Replay)
- ARD §"Audit Emission Pattern"
