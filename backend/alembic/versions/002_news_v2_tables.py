"""News V2 tables: news_articles, news_article_tickers, news_ingest_state, news_article_ticker_context

Revision ID: 002
Revises: 001
Create Date: 2026-03-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- news_articles ---
    op.create_table(
        "news_articles",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(30), nullable=False, server_default="finnhub"),
        sa.Column("provider_id", sa.String(200), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("raw_payload", JSONB(), nullable=True),
        sa.Column("sentiment_label", sa.String(20), nullable=True),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("sentiment_model", sa.String(50), nullable=True),
        sa.Column("sentiment_computed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("provider", "url", name="uq_news_article_provider_url"),
    )
    op.create_index("idx_news_articles_published", "news_articles", ["published_at"])
    op.create_index("idx_news_articles_provider", "news_articles", ["provider"])
    op.create_index("idx_news_articles_sentiment_null", "news_articles", ["sentiment_score"])

    # --- news_article_tickers ---
    op.create_table(
        "news_article_tickers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("article_id", sa.BigInteger(), sa.ForeignKey("news_articles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.UniqueConstraint("article_id", "ticker", name="uq_article_ticker"),
    )
    op.create_index("idx_article_tickers_ticker", "news_article_tickers", ["ticker"])
    op.create_index("idx_article_tickers_article", "news_article_tickers", ["article_id"])

    # --- news_ingest_state ---
    op.create_table(
        "news_ingest_state",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(30), nullable=False, server_default="finnhub"),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("last_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=True, server_default="ok"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.UniqueConstraint("provider", "ticker", name="uq_ingest_state_provider_ticker"),
    )

    # --- news_article_ticker_context ---
    op.create_table(
        "news_article_ticker_context",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("article_id", sa.BigInteger(), sa.ForeignKey("news_articles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("bar_date", sa.Date(), nullable=True),
        sa.Column("close_at_publish", sa.Float(), nullable=True),
        sa.Column("ret_1d", sa.Float(), nullable=True),
        sa.Column("ret_5d", sa.Float(), nullable=True),
        sa.Column("ret_20d", sa.Float(), nullable=True),
        sa.UniqueConstraint("article_id", "ticker", name="uq_context_article_ticker"),
    )
    op.create_index("idx_context_article", "news_article_ticker_context", ["article_id"])
    op.create_index("idx_context_ticker", "news_article_ticker_context", ["ticker"])


def downgrade() -> None:
    op.drop_table("news_article_ticker_context")
    op.drop_table("news_ingest_state")
    op.drop_table("news_article_tickers")
    op.drop_table("news_articles")
