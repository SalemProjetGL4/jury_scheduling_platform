"""drop project_domain table

Revision ID: 20260531_drop_project_domain
Revises: <previous_revision>
Create Date: 2026-05-31 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260531_drop_project_domain'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the association table if it exists. This is safe to run multiple times.
    op.execute("DROP TABLE IF EXISTS project_domain;")


def downgrade() -> None:
    # Recreate the table to restore previous schema state.
    op.create_table(
        'project_domain',
        sa.Column('project_id', sa.BigInteger(), nullable=False),
        sa.Column('domain_id', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('project_id', 'domain_id'),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['domain_id'], ['domain.id'], ondelete='CASCADE'),
    )
