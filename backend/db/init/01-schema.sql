-- =====================
-- CORE STRUCTURE
-- =====================

CREATE TABLE IF NOT EXISTS department (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS filiere (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    department_id BIGINT NOT NULL REFERENCES department(id)
);

CREATE TABLE IF NOT EXISTS domain (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL
);

-- =====================
-- USERS
-- =====================

CREATE TABLE IF NOT EXISTS professor (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    department_id BIGINT NOT NULL REFERENCES department(id),
    max_juries INT NOT NULL,
    preferences TEXT[]
);

CREATE TABLE IF NOT EXISTS student (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    promotion DATE NOT NULL,
    filiere_id BIGINT NOT NULL REFERENCES filiere(id)
);

-- =====================
-- MANY-TO-MANY RELATIONS
-- =====================

CREATE TABLE IF NOT EXISTS department_domain (
    department_id BIGINT REFERENCES department(id) ON DELETE CASCADE,
    domain_id BIGINT REFERENCES domain(id) ON DELETE CASCADE,
    PRIMARY KEY (department_id, domain_id)
);

CREATE TABLE IF NOT EXISTS professor_domain (
    professor_id BIGINT REFERENCES professor(id) ON DELETE CASCADE,
    domain_id BIGINT REFERENCES domain(id) ON DELETE CASCADE,
    PRIMARY KEY (professor_id, domain_id)
);

-- =====================
-- SESSION & SCHEDULING
-- =====================

CREATE TABLE IF NOT EXISTS room (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

INSERT INTO room (name) VALUES
    ('2B6-4'),
    ('2B6-3'),
    ('2B6-2'),
    ('2B6-1')
ON CONFLICT (name) DO NOTHING;

CREATE TABLE IF NOT EXISTS session (
    id BIGSERIAL PRIMARY KEY,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('planned', 'in_progress', 'completed'))
);

CREATE TABLE IF NOT EXISTS slot (
    id BIGSERIAL PRIMARY KEY,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    slot_number INT NOT NULL,
    room_id BIGINT NOT NULL REFERENCES room(id),
    session_id BIGINT NOT NULL REFERENCES session(id) ON DELETE CASCADE
);

-- =====================
-- PROJECTS
-- =====================

CREATE TABLE IF NOT EXISTS project (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    domain_id BIGINT NOT NULL REFERENCES domain(id),
    supervisor_id BIGINT NOT NULL REFERENCES professor(id),
    student_id BIGINT NOT NULL REFERENCES student(id)
);

-- =====================
-- CONSTRAINTS / LOGIC
-- =====================

CREATE TABLE IF NOT EXISTS unavailability (
    id BIGSERIAL PRIMARY KEY,
    professor_id BIGINT NOT NULL REFERENCES professor(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    period TEXT NOT NULL CHECK (period IN ('morning', 'afternoon', 'full_day'))
);

CREATE TABLE IF NOT EXISTS conflict (
    id BIGSERIAL PRIMARY KEY,
    professor_a BIGINT NOT NULL REFERENCES professor(id) ON DELETE CASCADE,
    professor_b BIGINT NOT NULL REFERENCES professor(id) ON DELETE CASCADE,
    CHECK (professor_a <> professor_b)
);

CREATE TABLE IF NOT EXISTS assignment (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES project(id),
    slot_id BIGINT NOT NULL REFERENCES slot(id) ON DELETE CASCADE,
    president_id BIGINT NOT NULL REFERENCES professor(id),
    examiner_id BIGINT NOT NULL REFERENCES professor(id)
);

CREATE TABLE IF NOT EXISTS constraint_rule (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('hard', 'soft')),
    weight NUMERIC(10, 2) NOT NULL,
    payload JSONB NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE
);