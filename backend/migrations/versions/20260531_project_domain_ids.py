"""migrate project.domain_id FK to domain_ids integer array

Revision ID: 20260531_project_domain_ids
Revises: 20260531_drop_project_domain
Create Date: 2026-05-31 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '20260531_project_domain_ids'
down_revision = '20260531_drop_project_domain'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('project', sa.Column('domain_ids', postgresql.ARRAY(sa.Integer()), nullable=True))
    op.execute("UPDATE project SET domain_ids = ARRAY[domain_id]::integer[] WHERE domain_id IS NOT NULL")
    op.execute("UPDATE project SET domain_ids = ARRAY[]::integer[] WHERE domain_ids IS NULL")
    op.alter_column('project', 'domain_ids', nullable=False, server_default='{}')
    op.drop_constraint('project_domain_id_fkey', 'project', type_='foreignkey')
    op.drop_column('project', 'domain_id')


def downgrade() -> None:
    op.add_column('project', sa.Column('domain_id', sa.Integer(), nullable=True))
    op.execute("UPDATE project SET domain_id = domain_ids[1] WHERE array_length(domain_ids, 1) > 0")
    op.alter_column('project', 'domain_id', nullable=False)
    op.create_foreign_key('project_domain_id_fkey', 'project', 'domain', ['domain_id'], ['id'])
    op.drop_column('project', 'domain_ids')
