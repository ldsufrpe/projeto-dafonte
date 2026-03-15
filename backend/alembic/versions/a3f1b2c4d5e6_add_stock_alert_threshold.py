"""add stock alert threshold

Revision ID: a3f1b2c4d5e6
Revises: 208cf538aa72
Create Date: 2026-03-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f1b2c4d5e6'
down_revision: Union[str, Sequence[str], None] = '208cf538aa72'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create stock_alert_threshold table."""
    op.create_table(
        'stock_alert_threshold',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('condominium_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column('min_quantity', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['condominium_id'], ['condominium.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['product.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('condominium_id', 'product_id', name='uq_stock_alert_threshold'),
    )
    op.create_index('ix_stock_alert_threshold_condominium_id', 'stock_alert_threshold', ['condominium_id'])
    op.create_index('ix_stock_alert_threshold_product_id', 'stock_alert_threshold', ['product_id'])


def downgrade() -> None:
    """Drop stock_alert_threshold table."""
    op.drop_index('ix_stock_alert_threshold_product_id', table_name='stock_alert_threshold')
    op.drop_index('ix_stock_alert_threshold_condominium_id', table_name='stock_alert_threshold')
    op.drop_table('stock_alert_threshold')
