"""Add description, sic_code, sic_description to tickers table.

Revision ID: 003
Revises: 002
"""

from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tickers", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("tickers", sa.Column("sic_code", sa.String(10), nullable=True))
    op.add_column("tickers", sa.Column("sic_description", sa.String(255), nullable=True))


def downgrade():
    op.drop_column("tickers", "sic_description")
    op.drop_column("tickers", "sic_code")
    op.drop_column("tickers", "description")
