"""Модели базы данных — User, Channel, VkMediaCache"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from bot.config import settings


class Base(DeclarativeBase):
    """Базовый класс для всех моделей"""
    pass


class User(Base):
    """Пользователь бота"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    download_count: Mapped[int] = mapped_column(default=0)
    language: Mapped[str] = mapped_column(String(5), default="ru")

    def __repr__(self) -> str:
        return f"<User {self.telegram_id} ({self.username})>"


class Channel(Base):
    """Канал/группа для обязательной подписки"""
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    title: Mapped[str] = mapped_column(String(255))
    invite_link: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Channel {self.channel_id} ({self.title})>"


def _default_expires() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=settings.cache_ttl_days)


class VkMediaCache(Base):
    """Кэш file_id для скачанных медиа из VK.

    Ключ кэша — composite: (source_url, quality, item_index).
    - Для одиночного видео/клипа: quality="360"/"720"/"1080"/..., item_index=0.
    - Для фото/документа: quality="photo" / "doc", item_index=0.
    - Для пост-карусели: quality="post", item_index=0..N (индекс элемента поста).
    """
    __tablename__ = "vk_media_cache"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_url: Mapped[str] = mapped_column(String(500), index=True)
    quality: Mapped[str] = mapped_column(String(50))
    item_index: Mapped[int] = mapped_column(Integer, default=0)
    # сколько всего элементов в посте (для quality="post"); для одиночных медиа = 1
    item_count: Mapped[int] = mapped_column(Integer, default=1)
    file_id: Mapped[str] = mapped_column(String(255))
    # media_type: video / audio / photo / document / animation
    media_type: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    hit_count: Mapped[int] = mapped_column(Integer, default=1)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_default_expires,
    )

    __table_args__ = (
        Index(
            "ix_vk_media_cache_key",
            "source_url", "quality", "item_index",
        ),
    )

    @property
    def is_expired(self) -> bool:
        # expires_at с tzinfo — приводим now к той же зоне
        now = datetime.now(self.expires_at.tzinfo) if self.expires_at.tzinfo else datetime.now(timezone.utc)
        return now > self.expires_at
