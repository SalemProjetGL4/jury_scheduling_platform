-- Create one scheduling session covering the September 2025 defence period.
INSERT INTO session (start_date, end_date, status)
VALUES ('2025-09-22', '2025-10-04', 'planned')
RETURNING id;

-- Create one slot per (date, period) from the real planning data.
-- All defences used room 2B6-4; slot_number=1 (only one room per half-day).
DO $$
DECLARE
    sess_id BIGINT;
    rid     BIGINT;
BEGIN
    SELECT id INTO sess_id FROM session ORDER BY id DESC LIMIT 1;
    SELECT id INTO rid     FROM room    WHERE name = '2B6-4';

    INSERT INTO slot (session_id, date, period, slot_number, room_id) VALUES
        (sess_id, '2025-09-22', 'morning',   1, rid),
        (sess_id, '2025-09-22', 'afternoon', 1, rid),
        (sess_id, '2025-09-23', 'morning',   1, rid),
        (sess_id, '2025-09-23', 'afternoon', 1, rid),
        (sess_id, '2025-09-24', 'morning',   1, rid),
        (sess_id, '2025-09-24', 'afternoon', 1, rid),
        (sess_id, '2025-09-25', 'morning',   1, rid),
        (sess_id, '2025-09-25', 'afternoon', 1, rid),
        (sess_id, '2025-09-26', 'morning',   1, rid),
        (sess_id, '2025-09-26', 'afternoon', 1, rid),
        (sess_id, '2025-09-27', 'morning',   1, rid),
        (sess_id, '2025-09-30', 'morning',   1, rid),
        (sess_id, '2025-09-30', 'afternoon', 1, rid),
        (sess_id, '2025-10-04', 'morning',   1, rid);
END $$;

-- Verify
SELECT s.id, s.date, s.period, r.name AS room
FROM slot s
JOIN room r ON r.id = s.room_id
ORDER BY s.date, s.period;
