"""Add unit_prefix and unit_number columns to unit table.

Revision ID: b7c2d3e4f5a6
Revises: a3f1b2c4d5e6
Create Date: 2026-03-14
"""
from alembic import op
import sqlalchemy as sa

revision = 'b7c2d3e4f5a6'
down_revision = 'a3f1b2c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('unit', sa.Column('unit_prefix', sa.String(20), nullable=True))
    op.add_column('unit', sa.Column('unit_number', sa.Integer(), nullable=True))

    # Populate from existing unit_code:
    # unit_prefix = everything before the trailing digits
    # unit_number = the trailing digits as integer
    op.execute("""
        UPDATE unit
        SET
            unit_prefix = regexp_replace(unit_code, '[0-9]+$', ''),
            unit_number  = CAST(regexp_replace(unit_code, '^.*[^0-9]', '') AS INTEGER)
        WHERE unit_code ~ '[0-9]+$'
    """)

    # Units that are purely numeric (no prefix)
    op.execute("""
        UPDATE unit
        SET
            unit_prefix = '',
            unit_number  = CAST(unit_code AS INTEGER)
        WHERE unit_code ~ '^[0-9]+$'
    """)


def downgrade() -> None:
    op.drop_column('unit', 'unit_number')
    op.drop_column('unit', 'unit_prefix')
