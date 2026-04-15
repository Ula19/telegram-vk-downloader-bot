"""CRUD операции с базой данных"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.models import Channel, User, VkMediaCache


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str | None,
    full_name: str,
    language: str | None = None,
) -> User:
    """Получить юзера или создать нового"""
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
            language=language or "ru",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    return user


async def get_user_language(session: AsyncSession, telegram_id: int) -> str:
    result = await session.execute(
        select(User.language).where(User.telegram_id == telegram_id)
    )
    lang = result.scalar_one_or_none()
    return lang or "ru"


async def update_user_language(
    session: AsyncSession, telegram_id: int, language: str
) -> None:
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    if user:
        user.language = language
        await session.commit()


async def increment_download_count(session: AsyncSession, telegram_id: int) -> None:
    """Инкремент счётчика скачиваний пользователя"""
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    if user:
        user.download_count = (user.download_count or 0) + 1
        await session.commit()


async def get_active_channels(session: AsyncSession) -> list[Channel]:
    result = await session.execute(select(Channel))
    return list(result.scalars().all())


async def add_channel(
    session: AsyncSession,
    channel_id: int,
    title: str,
    invite_link: str,
) -> Channel:
    result = await session.execute(
        select(Channel).where(Channel.channel_id == channel_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        # Передаём ID через args[0] — хендлер достанет и подставит в i18n-шаблон.
        raise ValueError(channel_id)

    channel = Channel(
        channel_id=channel_id,
        title=title,
        invite_link=invite_link,
    )
    session.add(channel)
    await session.commit()
    await session.refresh(channel)
    return channel


async def remove_channel(session: AsyncSession, channel_id: int) -> bool:
    result = await session.execute(
        select(Channel).where(Channel.channel_id == channel_id)
    )
    channel = result.scalar_one_or_none()
    if not channel:
        return False

    await session.delete(channel)
    await session.commit()
    return True


async def get_user_stats(session: AsyncSession) -> dict:
    from sqlalchemy import func as sa_func

    total = await session.execute(select(sa_func.count(User.id)))
    total_users = total.scalar() or 0

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_result = await session.execute(
        select(sa_func.count(User.id)).where(User.created_at >= today)
    )
    today_users = today_result.scalar() or 0

    downloads = await session.execute(
        select(sa_func.sum(User.download_count))
    )
    total_downloads = downloads.scalar() or 0

    channels = await session.execute(select(sa_func.count(Channel.id)))
    total_channels = channels.scalar() or 0

    return {
        "total_users": total_users,
        "today_users": today_users,
        "total_downloads": total_downloads,
        "total_channels": total_channels,
    }


async def get_all_user_ids(session: AsyncSession) -> list[int]:
    result = await session.execute(select(User.telegram_id))
    return [row[0] for row in result.all()]


# === VK media cache ===

async def get_cached_vk_media(
    session: AsyncSession,
    source_url: str,
    quality: str,
    item_index: int = 0,
) -> VkMediaCache | None:
    """Вернуть запись кэша если ещё жива. Протухшие записи возвращают None."""
    result = await session.execute(
        select(VkMediaCache).where(
            VkMediaCache.source_url == source_url,
            VkMediaCache.quality == quality,
            VkMediaCache.item_index == item_index,
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        return None
    if entry.is_expired:
        await session.delete(entry)
        await session.commit()
        return None
    entry.hit_count = (entry.hit_count or 0) + 1
    await session.commit()
    return entry


async def get_cached_vk_post(
    session: AsyncSession, source_url: str,
) -> list[VkMediaCache]:
    """Вернуть все элементы поста (quality='post'), отсортированные по item_index.
    Пустой список если кэш не полный/протух/целостность нарушена.

    Защита целостности: если сохранённый item_count не равен len(entries) —
    значит часть записей была потеряна (удалена/не сохранилась), возвращаем [].
    """
    result = await session.execute(
        select(VkMediaCache)
        .where(
            VkMediaCache.source_url == source_url,
            VkMediaCache.quality == "post",
        )
        .order_by(VkMediaCache.item_index)
    )
    entries = list(result.scalars().all())
    if not entries:
        return []
    # если хоть один элемент протух — считаем кэш невалидным
    for e in entries:
        if e.is_expired:
            return []
    # проверяем целостность: expected item_count должен совпадать с реальным числом записей
    expected = entries[0].item_count or 0
    if expected and len(entries) != expected:
        return []
    # инкрементируем hit
    for e in entries:
        e.hit_count = (e.hit_count or 0) + 1
    await session.commit()
    return entries


async def save_vk_media(
    session: AsyncSession,
    source_url: str,
    quality: str,
    file_id: str,
    media_type: str,
    item_index: int = 0,
    item_count: int = 1,
) -> VkMediaCache:
    """Сохранить или обновить запись кэша.

    Для постов/альбомов (quality="post") передавайте item_count — общее число
    элементов в посте (для проверки целостности кэша при чтении).
    """
    # если уже есть — обновляем
    result = await session.execute(
        select(VkMediaCache).where(
            VkMediaCache.source_url == source_url,
            VkMediaCache.quality == quality,
            VkMediaCache.item_index == item_index,
        )
    )
    entry = result.scalar_one_or_none()
    expires = datetime.now(timezone.utc) + timedelta(days=settings.cache_ttl_days)
    if entry is not None:
        entry.file_id = file_id
        entry.media_type = media_type
        entry.item_count = item_count
        entry.expires_at = expires
        await session.commit()
        return entry

    entry = VkMediaCache(
        source_url=source_url,
        quality=quality,
        item_index=item_index,
        item_count=item_count,
        file_id=file_id,
        media_type=media_type,
        expires_at=expires,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


async def cleanup_expired_vk_cache(session: AsyncSession) -> int:
    """Удаляет протухшие записи кэша. Возвращает число удалённых строк."""
    now = datetime.now(timezone.utc)
    result = await session.execute(
        delete(VkMediaCache).where(VkMediaCache.expires_at < now)
    )
    await session.commit()
    return result.rowcount or 0
