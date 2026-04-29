-- H2 hands-on snippet (supporting) — within-feed deduplication with audit emission.
--
-- Demonstrates BR-601 last-record-wins deduplication. Simple, runnable,
-- and satisfies the literal "duplicate PII" example in the PDF prompt.
-- This is the simple-SQL counterpart to the Splink headline snippet —
-- they answer different questions and both belong in the deck.
--
-- The PRD's H2 supporting snippet, lifted into a file that runs against
-- the prototype's staging table. Feed it via DuckDB or Postgres after
-- loading partner_a_day1.csv into a `staging_records` table with
-- columns (partner_id, partner_member_id, first_name, last_name, dob,
-- ssn_last_4, address, feed_line_number, feed_id, name_token).

-- ---------------------------------------------------------------------------
-- Part 1: identify duplicates within the feed and label winners/losers.
-- ---------------------------------------------------------------------------
WITH ranked AS (
    SELECT
        partner_id,
        partner_member_id,
        first_name, last_name, dob, ssn_last_4, address,
        feed_line_number,
        COUNT(*) OVER (
            PARTITION BY partner_id, partner_member_id
        ) AS dup_count,
        ROW_NUMBER() OVER (
            PARTITION BY partner_id, partner_member_id
            ORDER BY feed_line_number DESC
        ) AS reverse_rank,
        name_token
    FROM staging_records
    WHERE feed_id = :current_feed_id
)
SELECT
    partner_id,
    partner_member_id,
    feed_line_number,
    dup_count,
    CASE
        WHEN dup_count > 1 AND reverse_rank = 1 THEN 'DEDUP_WINNER'
        WHEN dup_count > 1                       THEN 'DEDUP_LOSER'
        ELSE                                          'UNIQUE'
    END AS dedup_status
FROM ranked
ORDER BY partner_id, partner_member_id, feed_line_number;


-- ---------------------------------------------------------------------------
-- Part 2: emit one audit event per dedup_winner (XR-005 — tokens only,
-- never plaintext PII; the dedup loser is referenced by feed_line_number).
-- ---------------------------------------------------------------------------
INSERT INTO audit_event (event_class, target_token, context, ts)
SELECT
    'WITHIN_FEED_DEDUP',
    name_token,
    jsonb_build_object(
        'partner_id',         partner_id,
        'partner_member_id',  partner_member_id,
        'duplicate_count',    dup_count,
        'kept_line',          feed_line_number,
        'feed_id',            :current_feed_id
    ),
    NOW()
FROM (
    SELECT
        partner_id,
        partner_member_id,
        feed_line_number,
        name_token,
        COUNT(*) OVER (PARTITION BY partner_id, partner_member_id) AS dup_count,
        ROW_NUMBER() OVER (
            PARTITION BY partner_id, partner_member_id
            ORDER BY feed_line_number DESC
        ) AS reverse_rank
    FROM staging_records
    WHERE feed_id = :current_feed_id
) ranked
WHERE dup_count > 1 AND reverse_rank = 1;
