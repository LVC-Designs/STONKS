from sqlalchemy import Column, Integer, Numeric, String, Text, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.sql import func
from app.database import Base


class NewsItem(Base):
    __tablename__ = "news_items"

    id = Column(Integer, primary_key=True)
    ticker_id = Column(Integer, ForeignKey("tickers.id"), nullable=True)
    symbol = Column(String(20))
    source_id = Column(String(100))
    source = Column(String(30))
    headline = Column(String(500), nullable=False)
    summary = Column(Text)
    url = Column(String(1000))
    image_url = Column(String(1000))
    published_at = Column(DateTime(timezone=True), nullable=False)
    category = Column(String(50))
    sentiment_score = Column(Numeric(5, 4))
    sentiment_label = Column(String(20))
    related_tickers = Column(String(200))
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_news_source_id"),
        Index("idx_news_ticker_date", "ticker_id", "published_at"),
        Index("idx_news_published", "published_at"),
    )
