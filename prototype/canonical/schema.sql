-- Canonical eligibility store — A5 from PROTOTYPE_PRD.md.
--
-- Six-table operational schema lifted from
-- docs/ARCHITECTURE_REQUIREMENTS.md "Data Schemas" section. The production
-- target is AlloyDB; the prototype runs on local Postgres 17. The DDL is
-- portable across both because we use only standard PostgreSQL types.
--
-- The audit_event table is intentionally absent here — in production it lives
-- in BigQuery; in the prototype it is a JSONL hash chain (A8), not a SQL
-- table.
--
-- State transitions are enforced by application code (see state_machine.py)
-- per BR-202 — not by trigger — so the transition table remains testable in
-- isolation.

-- ---------------------------------------------------------------------------
-- canonical_member
-- ---------------------------------------------------------------------------
CREATE TABLE canonical_member (
    member_id            UUID         PRIMARY KEY,
    state                TEXT         NOT NULL CHECK (state IN (
                                          'PENDING_RESOLUTION',
                                          'ELIGIBLE_ACTIVE',
                                          'ELIGIBLE_GRACE',
                                          'INELIGIBLE',
                                          'DELETED'
                                      )),
    state_effective_from TIMESTAMPTZ  NOT NULL,
    state_effective_to   TIMESTAMPTZ,
    -- tokenized identifiers (joinable, deterministic non-FPE per AD-009)
    name_token           TEXT         NOT NULL,
    dob_token            TEXT         NOT NULL,
    -- tokenized identifiers (non-joinable, vault-resolvable only)
    address_token        TEXT,
    phone_token          TEXT,
    email_token          TEXT,
    ssn_token            TEXT,
    -- metadata
    first_seen_at        TIMESTAMPTZ  NOT NULL,
    last_updated_at      TIMESTAMPTZ  NOT NULL,
    tombstoned_at        TIMESTAMPTZ
);

CREATE INDEX idx_canonical_member_state ON canonical_member(state);
CREATE INDEX idx_canonical_member_anchor ON canonical_member(name_token, dob_token);


-- ---------------------------------------------------------------------------
-- partner_enrollment
-- ---------------------------------------------------------------------------
-- One-to-many from canonical_member; implements BR-205 attribution neutrality.
-- No "primary partner" column — multiple simultaneous enrollments are
-- first-class.
CREATE TABLE partner_enrollment (
    enrollment_id        UUID         PRIMARY KEY,
    member_id            UUID         NOT NULL REFERENCES canonical_member(member_id),
    partner_id           TEXT         NOT NULL,
    partner_member_id    TEXT         NOT NULL,
    effective_from       DATE         NOT NULL,
    effective_to         DATE,
    last_seen_in_feed_at TIMESTAMPTZ  NOT NULL,
    -- partner-supplied attributes (tokenized)
    partner_attributes   JSONB        NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (partner_id, partner_member_id, effective_from)
);

CREATE INDEX idx_partner_enrollment_member ON partner_enrollment(member_id);
CREATE INDEX idx_partner_enrollment_active
    ON partner_enrollment(member_id) WHERE effective_to IS NULL;


-- ---------------------------------------------------------------------------
-- member_history (SCD2)
-- ---------------------------------------------------------------------------
-- Operational window only (90 days per AD-005). Production replicates to
-- BigQuery for unbounded retention via Datastream; the prototype's analytical
-- copy is produced by a periodic sync script writing to DuckDB.
CREATE TABLE member_history (
    history_id           BIGSERIAL    PRIMARY KEY,
    member_id            UUID         NOT NULL REFERENCES canonical_member(member_id),
    state                TEXT         NOT NULL,
    state_effective_from TIMESTAMPTZ  NOT NULL,
    state_effective_to   TIMESTAMPTZ,
    name_token           TEXT,
    dob_token            TEXT,
    address_token        TEXT,
    phone_token          TEXT,
    email_token          TEXT,
    ssn_token            TEXT,
    change_trigger       TEXT         NOT NULL,
    change_event_id      UUID         NOT NULL
);

CREATE INDEX idx_member_history_member_time
    ON member_history(member_id, state_effective_from);
CREATE INDEX idx_member_history_change_event
    ON member_history(change_event_id);


-- ---------------------------------------------------------------------------
-- match_decision
-- ---------------------------------------------------------------------------
-- One row per identity-resolution outcome. Algorithm + config version stamps
-- support BR-104 (match replay continuity). score_breakdown retains Splink's
-- per-comparison weights for explainability.
CREATE TABLE match_decision (
    decision_id          UUID         PRIMARY KEY,
    candidate_record_ref TEXT         NOT NULL,
    resolved_member_id   UUID         REFERENCES canonical_member(member_id),
    tier_outcome         TEXT         NOT NULL CHECK (tier_outcome IN (
                                          'TIER_1_DETERMINISTIC',
                                          'TIER_2_PROB_HIGH',
                                          'TIER_3_PROB_REVIEW',
                                          'TIER_4_DISTINCT'
                                      )),
    score                NUMERIC(8, 6),
    algorithm_version    TEXT         NOT NULL,
    config_version       TEXT         NOT NULL,
    decided_at           TIMESTAMPTZ  NOT NULL,
    score_breakdown      JSONB
);

CREATE INDEX idx_match_decision_member ON match_decision(resolved_member_id);
CREATE INDEX idx_match_decision_tier ON match_decision(tier_outcome);


-- ---------------------------------------------------------------------------
-- deletion_ledger
-- ---------------------------------------------------------------------------
-- Holds one-way hashes only — no recoverable PII per BR-703. Identity
-- Resolution queries this table on every staging record before publication;
-- a hash hit routes the record to SUPPRESSED_DELETED rather than
-- ELIGIBLE_ACTIVE.
CREATE TABLE deletion_ledger (
    ledger_id            BIGSERIAL    PRIMARY KEY,
    suppression_hash     TEXT         NOT NULL UNIQUE,
    deleted_at           TIMESTAMPTZ  NOT NULL,
    deletion_request_id  UUID         NOT NULL,
    override_count       INT          NOT NULL DEFAULT 0
);

CREATE INDEX idx_deletion_ledger_hash ON deletion_ledger(suppression_hash);


-- ---------------------------------------------------------------------------
-- review_queue
-- ---------------------------------------------------------------------------
-- Tier 3 outcomes from BR-101 land here. Reviewers see tokenized references
-- only; resolving a queue item to MERGE triggers a state transition on the
-- canonical record.
CREATE TABLE review_queue (
    queue_id             UUID         PRIMARY KEY,
    decision_id          UUID         NOT NULL REFERENCES match_decision(decision_id),
    candidate_record_ref TEXT         NOT NULL,
    candidate_member_ids UUID[]       NOT NULL,
    score                NUMERIC(8, 6) NOT NULL,
    queued_at            TIMESTAMPTZ  NOT NULL,
    claimed_by           TEXT,
    claimed_at           TIMESTAMPTZ,
    resolved_at          TIMESTAMPTZ,
    resolution           TEXT         CHECK (resolution IN ('MERGE', 'DISTINCT', 'ESCALATE'))
);

CREATE INDEX idx_review_queue_unresolved
    ON review_queue(queued_at) WHERE resolved_at IS NULL;
