CREATE TABLE IF NOT EXISTS filiere (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS domain (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    filiere_id BIGINT NOT NULL REFERENCES filiere(id)
);

CREATE TABLE IF NOT EXISTS professor (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    specialities TEXT[] NOT NULL,
    max_juries INT NOT NULL,
    domain BIGINT NOT NULL REFERENCES domain(id)
);

CREATE TABLE IF NOT EXISTS student (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    promotion_year INT NOT NULL,
    filiere_id BIGINT NOT NULL REFERENCES filiere(id)
);

CREATE TABLE IF NOT EXISTS session (
    id BIGSERIAL PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('planned', 'in_progress', 'completed')),
    date DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS project (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    domain BIGINT NOT NULL REFERENCES domain(id),
    supervisor_id BIGINT NOT NULL REFERENCES professor(id),
    student_id BIGINT NOT NULL REFERENCES student(id)
);

CREATE TABLE IF NOT EXISTS slot (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    period TEXT NOT NULL CHECK (period IN ('morning', 'afternoon')),
    slot_number INT NOT NULL,
    room TEXT NOT NULL,
    session_id BIGINT NOT NULL REFERENCES session(id) ON DELETE CASCADE
);

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
    examiner_id BIGINT NOT NULL REFERENCES professor(id),
    project_id BIGINT NOT NULL REFERENCES project(id),
    president_id BIGINT NOT NULL REFERENCES professor(id),
    slot_id BIGINT NOT NULL REFERENCES slot(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS constraint_rule (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('hard', 'soft')),
    weight NUMERIC(10, 2) NOT NULL,
    payload JSONB NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE
);