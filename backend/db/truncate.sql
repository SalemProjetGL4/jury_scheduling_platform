-- Truncate all tables in reverse dependency order and reset sequences.
-- room is intentionally excluded so the 4 static rooms survive a data reset.
TRUNCATE TABLE
    assignment,
    conflict,
    unavailability,
    slot,
    project,
    professor_domain,
    department_domain,
    constraint_rule,
    "session",
    student,
    professor,
    domain,
    filiere,
    department
CASCADE;

DO $$
DECLARE r RECORD;
BEGIN
    FOR r IN
        SELECT sequence_name
        FROM information_schema.sequences
        WHERE sequence_schema = 'public'
    LOOP
        EXECUTE format('ALTER SEQUENCE %I RESTART WITH 1', r.sequence_name);
    END LOOP;
END $$;
