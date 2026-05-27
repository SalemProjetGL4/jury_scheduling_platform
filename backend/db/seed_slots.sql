-- Create session
INSERT INTO session (start_date, end_date, status)
VALUES ('2025-09-22', '2025-10-04', 'planned');

DO $$
DECLARE
    sess_id BIGINT;
    rid     BIGINT;
BEGIN
    SELECT id INTO sess_id
    FROM session
    ORDER BY id DESC
    LIMIT 1;

    SELECT id INTO rid
    FROM room
    WHERE name = '2B6-4';

    INSERT INTO slot (
        session_id,
        start_time,
        end_time,
        slot_number,
        room_id
    ) VALUES

    -- 22 Sept morning
    (sess_id, '2025-09-22 08:00:00', '2025-09-22 09:00:00', 1, rid),
    (sess_id, '2025-09-22 09:00:00', '2025-09-22 10:00:00', 2, rid),
    (sess_id, '2025-09-22 10:00:00', '2025-09-22 11:00:00', 3, rid),
    (sess_id, '2025-09-22 11:00:00', '2025-09-22 12:00:00', 4, rid),

    -- 22 Sept afternoon
    (sess_id, '2025-09-22 13:00:00', '2025-09-22 14:00:00', 5, rid),
    (sess_id, '2025-09-22 14:00:00', '2025-09-22 15:00:00', 6, rid),
    (sess_id, '2025-09-22 15:00:00', '2025-09-22 16:00:00', 7, rid),
    (sess_id, '2025-09-22 16:00:00', '2025-09-22 17:00:00', 8, rid);

END $$;
