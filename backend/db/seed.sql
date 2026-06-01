-- Seed script generated from backend/app/seed.py::seed()
-- Clears tables then inserts deterministic sample data.

BEGIN;

TRUNCATE TABLE
  assignment,
  conflict,
  unavailability,
  professor_domain,
  department_domain,
  slot,
  project,
  constraint_rule,
  session,
  room,
  student,
  professor,
  domain,
  filiere,
  department
RESTART IDENTITY CASCADE;

-- Departments
INSERT INTO department (id, name) VALUES
  (1, 'Computer Science Department'),
  (2, 'Data Science Department');

-- Filieres
INSERT INTO filiere (id, name, department_id) VALUES
  (1, 'Computer Science', 1),
  (2, 'Data Science', 2);

-- Canonical domains (order matches CANONICAL_DOMAINS list)
INSERT INTO domain (id, name) VALUES
  (1, 'Artificial Intelligence'),
  (2, 'Machine Learning'),
  (3, 'Data Science'),
  (4, 'Data Engineering'),
  (5, 'Internet of Things'),
  (6, 'Security'),
  (7, 'Cloud'),
  (8, 'DevOps'),
  (9, 'Web Development'),
  (10, 'Mobile'),
  (11, 'Blockchain'),
  (12, 'Networking'),
  (13, 'Embedded Systems'),
  (14, 'Natural Language Processing'),
  (15, 'Computer Vision'),
  (16, 'Databases'),
  (17, 'Human-Computer Interaction'),
  (18, 'Bioinformatics'),
  (19, 'Finance'),
  (20, 'Healthcare'),
  (21, 'Robotics'),
  (22, 'Distributed Systems'),
  (23, 'Software Engineering'),
  (24, 'Deep Learning'),
  (25, 'Big Data'),
  (26, 'MLOps'),
  (27, 'Edge Computing'),
  (28, 'Quantum Computing'),
  (29, 'Computer Graphics'),
  (30, 'Augmented Reality'),
  (31, 'Virtual Reality'),
  (32, 'Game Development'),
  (33, 'Information Retrieval'),
  (34, 'Operating Systems'),
  (35, 'Compilers'),
  (36, 'Formal Methods'),
  (37, 'Algorithm Design'),
  (38, 'Digital Twins'),
  (39, 'Simulation'),
  (40, 'Autonomous Systems'),
  (41, 'FinTech');

-- Department-domain mappings
INSERT INTO department_domain (department_id, domain_id) VALUES
  (1, 1),
  (1, 2),
  (2, 3);

-- Professors
INSERT INTO professor (id, name, email, department_id, max_juries, preferences) VALUES
  (1, 'Dr. Amina Rami', 'amina.rami@example.com', 1, 4, ARRAY['optimization', 'scheduling']::text[]),
  (2, 'Dr. Karim Haddad', 'karim.haddad@example.com', 2, 3, ARRAY['machine-learning', 'data-mining']::text[]),
  (3, 'Dr. Salma Idrissi', 'salma.idrissi@example.com', 1, 5, ARRAY['software-architecture', 'testing']::text[]);

-- Professor-domain mappings
INSERT INTO professor_domain (professor_id, domain_id) VALUES
  (1, 1),
  (2, 3),
  (3, 2);

-- Students
INSERT INTO student (id, name, email, promotion, filiere_id) VALUES
  (1, 'Youssef Benali', 'youssef.benali@example.com', DATE '2026-01-01', 1),
  (2, 'Lina Amrani', 'lina.amrani@example.com', DATE '2026-01-01', 2);

-- Sessions
INSERT INTO session (id, status, start_date, end_date) VALUES
  (1, 'planned', DATE '2026-06-22', DATE '2026-06-22'),
  (2, 'planned', DATE '2026-06-23', DATE '2026-06-23');

-- Projects (domain_ids is a PostgreSQL int[])
INSERT INTO project (id, title, domain_ids, supervisor_id, student_id, session_id, enterprise, enterprise_supervisor) VALUES
  (1, 'Adaptive Jury Scheduling', ARRAY[1]::int[], 1, 1, 1, NULL, NULL),
  (2, 'Learning Analytics Dashboard', ARRAY[3]::int[], 2, 2, 2, NULL, NULL);

-- Rooms
INSERT INTO room (id, name) VALUES
  (1, '2B6-4'),
  (2, '2B6-3');

-- Slots
INSERT INTO slot (id, start_time, end_time, slot_number, room_id, session_id) VALUES
  (1, TIMESTAMP '2026-06-22 08:00:00', TIMESTAMP '2026-06-22 09:00:00', 1, 1, 1),
  (2, TIMESTAMP '2026-06-23 13:00:00', TIMESTAMP '2026-06-23 14:00:00', 1, 2, 2);

-- Unavailabilities
INSERT INTO unavailability (id, professor_id, date, period) VALUES
  (1, 1, DATE '2026-06-23', 'afternoon'),
  (2, 2, DATE '2026-06-22', 'morning');

-- Conflicts
INSERT INTO conflict (id, professor_a, professor_b) VALUES
  (1, 1, 2);

-- Assignments
INSERT INTO assignment (id, examiner_id, project_id, president_id, slot_id) VALUES
  (1, 2, 1, 3, 1),
  (2, 1, 2, 3, 2);

-- Constraint rules
INSERT INTO constraint_rule (id, name, type, weight, payload, enabled) VALUES
  (1, 'No Double Booking', 'hard', 1.00, '{"rule": "no_overlap_for_professor"}'::json, TRUE),
  (2, 'Preferred Morning Slots', 'soft', 0.50, '{"rule": "prefer_morning"}'::json, TRUE);

-- Ensure sequences continue after explicit IDs.
SELECT setval(pg_get_serial_sequence('department', 'id'), COALESCE((SELECT MAX(id) FROM department), 1), TRUE);
SELECT setval(pg_get_serial_sequence('filiere', 'id'), COALESCE((SELECT MAX(id) FROM filiere), 1), TRUE);
SELECT setval(pg_get_serial_sequence('domain', 'id'), COALESCE((SELECT MAX(id) FROM domain), 1), TRUE);
SELECT setval(pg_get_serial_sequence('professor', 'id'), COALESCE((SELECT MAX(id) FROM professor), 1), TRUE);
SELECT setval(pg_get_serial_sequence('student', 'id'), COALESCE((SELECT MAX(id) FROM student), 1), TRUE);
SELECT setval(pg_get_serial_sequence('session', 'id'), COALESCE((SELECT MAX(id) FROM session), 1), TRUE);
SELECT setval(pg_get_serial_sequence('project', 'id'), COALESCE((SELECT MAX(id) FROM project), 1), TRUE);
SELECT setval(pg_get_serial_sequence('room', 'id'), COALESCE((SELECT MAX(id) FROM room), 1), TRUE);
SELECT setval(pg_get_serial_sequence('slot', 'id'), COALESCE((SELECT MAX(id) FROM slot), 1), TRUE);
SELECT setval(pg_get_serial_sequence('unavailability', 'id'), COALESCE((SELECT MAX(id) FROM unavailability), 1), TRUE);
SELECT setval(pg_get_serial_sequence('conflict', 'id'), COALESCE((SELECT MAX(id) FROM conflict), 1), TRUE);
SELECT setval(pg_get_serial_sequence('assignment', 'id'), COALESCE((SELECT MAX(id) FROM assignment), 1), TRUE);
SELECT setval(pg_get_serial_sequence('constraint_rule', 'id'), COALESCE((SELECT MAX(id) FROM constraint_rule), 1), TRUE);

COMMIT;
