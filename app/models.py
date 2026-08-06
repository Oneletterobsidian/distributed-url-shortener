"""
数据模型：ShortLink（短链接表）+ ClickEvent（点击记录表）
"""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ShortLink(Base):
    """短码 -> 长链接的核心映射表。短码本身做主键（自然键）。"""

    __tablename__ = "short_links"

    short_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    long_url: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_instance: Mapped[str] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    clicks: Mapped[list["ClickEvent"]] = relationship(
        back_populates="short_link", cascade="all, delete-orphan"
    )


class ClickEvent(Base):
    """每一次点击的精确记录，短码作为外键指向ShortLink表。"""

    __tablename__ = "click_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    short_code: Mapped[str] = mapped_column(
        String(16), ForeignKey("short_links.short_code", ondelete="CASCADE")
    )
    clicked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    short_link: Mapped["ShortLink"] = relationship(back_populates="clicks")

    __table_args__ = (
        Index("ix_click_events_short_code_clicked_at", "short_code", "clicked_at"),
    )