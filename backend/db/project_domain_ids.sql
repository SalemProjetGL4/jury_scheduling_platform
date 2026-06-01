BEGIN;

ALTER TABLE project
    ADD COLUMN IF NOT EXISTS domain_ids INTEGER[] DEFAULT '{}'::integer[];

UPDATE project
SET domain_ids = ARRAY[domain_id]::integer[]
WHERE domain_id IS NOT NULL;

ALTER TABLE project
    ALTER COLUMN domain_ids SET NOT NULL;

ALTER TABLE project
    DROP CONSTRAINT IF EXISTS project_domain_id_fkey;

ALTER TABLE project
    DROP COLUMN IF EXISTS domain_id;

COMMIT;