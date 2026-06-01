-- Merge sessions 5, 6, 7 into session 4.
-- All four cover the same date range (2026-09-22 → 2026-09-26) and were created
-- one per room due to a now-fixed bug. Assignments reference slot_id directly
-- and are unaffected by this change.

BEGIN;

-- Reassign all slots from the duplicate sessions to session 4
UPDATE slot
SET session_id = 4
WHERE session_id IN (5, 6, 7);

-- Remove the now-empty duplicate sessions
DELETE FROM session
WHERE id IN (5, 6, 7);

COMMIT;
