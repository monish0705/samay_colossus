"""market_data_engineering_pipeline

Revision ID: a1b2c3d4e5f6
Revises: cee3e9392b8d
Create Date: 2026-11-09 22:56:00
"""
import app.db
import sqlalchemy as sa
from alembic import op

revision = 'a1b2c3d4e5f6'
down_revision = 'cee3e9392b8d'
branch_labels = None
depends_on = None

def upgrade():
    # Add columns to markets
    with op.batch_alter_table('markets') as batch_op:
        batch_op.add_column(sa.Column('latitude', sa.Numeric(precision=9, scale=6), nullable=True))
        batch_op.add_column(sa.Column('longitude', sa.Numeric(precision=9, scale=6), nullable=True))

    # Add columns to commodities
    with op.batch_alter_table('commodities') as batch_op:
        batch_op.add_column(sa.Column('category', sa.String(length=64), nullable=False, server_default='Produce'))
        batch_op.add_column(sa.Column('standard_unit', sa.String(length=32), nullable=False, server_default='INR/quintal'))
        batch_op.add_column(sa.Column('perishability_class', sa.String(length=64), nullable=False, server_default='perishable'))

    # Create market_prices table
    op.create_table(
        'market_prices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('commodity', sa.String(length=64), nullable=False),
        sa.Column('variety', sa.String(length=120), nullable=False, server_default='unspecified'),
        sa.Column('grade', sa.String(length=64), nullable=False, server_default='unspecified'),
        sa.Column('market_name', sa.String(length=120), nullable=False),
        sa.Column('district', sa.String(length=64), nullable=False),
        sa.Column('state', sa.String(length=64), nullable=False, server_default='Karnataka'),
        sa.Column('arrival_date', sa.Date(), nullable=False),
        sa.Column('minimum_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('maximum_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('modal_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('price_unit', sa.String(length=32), nullable=False, server_default='INR/quintal'),
        sa.Column('source', sa.String(length=255), nullable=False),
        sa.Column('source_record_id', sa.String(length=120), nullable=True),
        sa.Column('raw_unit', sa.String(length=64), nullable=True),
        sa.Column('is_outlier', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('data_status', sa.String(length=32), nullable=False, server_default='CACHED'),
        sa.Column('imported_at', app.db.UTCDateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('commodity', 'variety', 'market_name', 'arrival_date', name='uq_market_price_series_date'),
        sa.CheckConstraint('minimum_price >= 0 AND minimum_price <= modal_price AND modal_price <= maximum_price', name='ck_price_order')
    )

def downgrade():
    op.execute(sa.text("PRAGMA foreign_keys=OFF"))
    op.drop_table('market_prices')
    op.execute(sa.text("PRAGMA foreign_keys=ON"))
