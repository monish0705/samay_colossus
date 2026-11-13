"""Align market_prices timestamps with the ORM Record base."""
import sqlalchemy as sa
from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("market_prices") as batch:
        batch.add_column(sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE market_prices SET created_at = imported_at WHERE created_at IS NULL")


def downgrade():
    with op.batch_alter_table("market_prices") as batch:
        batch.drop_column("created_at")
