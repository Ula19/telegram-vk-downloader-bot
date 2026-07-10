"""Хэндлер скачивания VK-медиа.

Флоу:
  1) URL → detect_vk_media_type
  2) Для video/clip/video_ext → get_media_info → выбор качества → download_video → отправка
  3) Для doc → download_doc → отправка (video/audio/animation/document по расширению)
  4) Для photo → download_photo → send_photo
  5) Для album / wall_post → download_post_attachments → send_media_group чанками по 10
  6) Для story → download_photo (gallery-dl умеет)
  7) channel / unknown → ошибка "unsupported_type"

Кэш:
  * видео: ключ (url, quality, 0)
  * одиночное фото/doc: (url, "photo"|"doc", 0)
  * пост/альбом: (url, "post", i) для каждого item

Cleanup: Local Bot API НЕ чистит файлы — делаем это сами, всегда, в try/finally.
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import tempfile
import time
from pathlib import Path

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    FSInputFile,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
)

from bot.config import settings
from bot.database import async_session
from bot.emojis import E
from bot.database.crud import (
    get_cached_vk_media,
    get_cached_vk_post,
    get_user_language,
    increment_download_count,
    save_vk_media,
)
from bot.i18n import t
from bot.keyboards.inline import get_back_keyboard, get_quality_keyboard
from bot.services.vk import (
    ContentUnavailableError,
    FileTooLargeError,
    LiveStreamError,
    MusicNotSupportedError,
    PrivateContentError,
    VkDownloadError,
    downloader,
)
from bot.services.vk_extractor import (
    VkMediaType,
    detect_vk_media_type,
    normalize_vk_url,
    resolve_short_link,
)
from bot.utils.helpers import extract_vk_url, format_duration, is_vk_url
from bot.utils.split import split_video

logger = logging.getLogger(__name__)
router = Router()

# Интервал между обновлениями прогресс-бара (сек) — Telegram не любит частые edit'ы.
PROGRESS_UPDATE_INTERVAL = 4

# троттлинг алертов о fallback — одно сообщение раз в N секунд на (источник+категория)
_FALLBACK_ALERT_THROTTLE = 600  # 10 минут
_last_fallback_alert: dict[str, float] = {}

# человеко-понятные подписи к категориям ошибок для админ-алерта
_ERROR_CATEGORY_LABELS = {
    "cookies_expired": "Cookies протухли — обнови через /update_cookies",
    "network": "Сетевая ошибка (таймаут/нет связи)",
    "too_large": "Файл слишком большой",
    "unknown": "Неизвестная ошибка",
}

# категории НЕ алертим — это ошибки контента, не инфраструктуры
_SILENT_CATEGORIES = {"private", "not_found", "geo_blocked", "live", "music_unsupported", "bad_url"}

# bot instance устанавливается из main.py через setup_fallback_alerts
_bot_ref = None


def setup_fallback_alerts(bot) -> None:
    """Подключает callback алертов админу к downloader.

    Вызывается из main.py после создания бота.
    """
    global _bot_ref
    _bot_ref = bot
    from bot.services.vk import downloader as _dl
    _dl.on_source_failed = _on_source_failed
    logger.info("Алерты о падении источников подключены")


def _on_source_failed(source: str, error: str) -> None:
    """Sync callback — шедулит асинхронную отправку алерта в event loop."""
    if _bot_ref is None:
        return
    try:
        asyncio.create_task(_send_fallback_alert(source, error))
    except RuntimeError:
        pass


async def _send_fallback_alert(source: str, error: str) -> None:
    """Отправляет алерт админу о падении источника. С троттлингом и классификацией."""
    from bot.services.vk import classify_error
    now = time.time()
    category = classify_error(error)

    # пропускаем user/content ошибки — не спамим админа
    if category in _SILENT_CATEGORIES:
        return

    # WARP получил блок IP — перезапускаем для смены IP
    if source == "warp" and category in ("network", "unknown"):
        from bot.utils.docker import restart_warp
        restarted = await restart_warp()
        if restarted:
            logger.info("WARP перезапущен после сбоя: %s", category)

    throttle_key = f"{source}:{category}"
    last = _last_fallback_alert.get(throttle_key, 0)
    if now - last < _FALLBACK_ALERT_THROTTLE:
        return
    _last_fallback_alert[throttle_key] = now

    short_error = error[:300] + "..." if len(error) > 300 else error
    category_label = _ERROR_CATEGORY_LABELS.get(category, category)

    warp_note = ""
    if source == "warp":
        warp_note = "\n\n♻️ <i>WARP контейнер перезапущен для смены IP</i>"

    text = (
        f"{E['warning']} <b>Источник упал!</b>\n\n"
        f"<b>Источник:</b> {source}\n"
        f"<b>Категория:</b> {category_label}\n"
        f"<b>Ошибка:</b> <code>{short_error}</code>"
        f"{warp_note}"
    )

    for admin_id in settings.admin_id_list:
        try:
            await _bot_ref.send_message(admin_id, text, parse_mode="HTML")
            logger.info("Админ %s уведомлён о падении %s (%s)", admin_id, source, category)
        except Exception as e:
            logger.warning("Не удалось уведомить админа %s: %s", admin_id, e)


def _make_progress_bar(lang: str, percent: int, dl_mb: float, total_mb: float) -> str:
    """Рисует полоску прогресса для статус-сообщения."""
    filled = max(0, min(12, int(percent / 100 * 12)))
    bar = "▰" * filled + "▱" * (12 - filled)
    return t(
        "download.progress", lang,
        bar=bar, percent=percent, dl=f"{dl_mb:.0f}", total=f"{total_mb:.0f}",
    )


async def _safe_edit(msg: Message, text: str) -> None:
    """Безопасный edit_text — игнорируем Telegram rate-limit и 'message not modified'."""
    try:
        await msg.edit_text(text, parse_mode="HTML")
    except Exception:
        pass


class DownloadStates(StatesGroup):
    choosing_quality = State()


# ==================== ENTRY POINT ====================

@router.message(F.text)
async def handle_vk_url(message: Message, state: FSMContext) -> None:
    """Обработка текстовых сообщений — ищем ссылки VK.

    Если текст — не VK-ссылка (любой другой текст, включая "прив" и ссылки
    других сайтов), отвечаем подсказкой по паттерну Instagram-бота.
    """
    try:
        text = (message.text or "").strip()

        async with async_session() as session:
            lang = await get_user_language(session, message.from_user.id)

        if not is_vk_url(text):
            await message.answer(t("download.not_vk", lang), parse_mode="HTML")
            return

        # В тексте может быть ссылка + мусор (юзер вставил лог/конфиг со ссылкой) —
        # берём именно VK-URL, иначе движок получит весь блок и упадёт "Failed to parse".
        raw = extract_vk_url(text) or text
        # Короткие vk.cc / vk.link — раскрываем в полный URL до детекта типа.
        resolved = await resolve_short_link(raw)
        url = normalize_vk_url(resolved)
        media_type = detect_vk_media_type(url)

        if media_type in (VkMediaType.UNKNOWN, VkMediaType.CHANNEL):
            await message.answer(
                t("error.unsupported_type", lang),
                reply_markup=get_back_keyboard(lang),
                parse_mode="HTML",
            )
            return
    except Exception as e:
        logger.exception("handle_vk_url: %s", e)
        try:
            await message.answer(t("error.generic", "ru"), parse_mode="HTML")
        except Exception:
            pass
        return

    # Для single video/clip/video_ext — показываем выбор качества.
    # Для всего остального — скачиваем сразу.
    if media_type in (VkMediaType.VIDEO, VkMediaType.CLIP, VkMediaType.VIDEO_EXT):
        await _handle_video_flow(message, state, url, media_type.value, lang)
        return

    if media_type == VkMediaType.DOC:
        await _handle_doc_flow(message, url, lang)
        return

    if media_type == VkMediaType.PHOTO:
        await _handle_photo_flow(message, url, lang, quality_key="photo")
        return

    if media_type == VkMediaType.STORY:
        # VK-сторис нельзя вытащить ни yt-dlp (нет экстрактора), ни gallery-dl
        # (принимает story-URL за screen name → 0 файлов). Нужен VK API + токен.
        # Пока честно говорим, что не поддерживается, вместо ложного «видео удалено».
        await message.answer(
            t("error.story_unsupported", lang),
            reply_markup=get_back_keyboard(lang),
            parse_mode="HTML",
        )
        return

    if media_type in (VkMediaType.ALBUM, VkMediaType.WALL_POST):
        await _handle_post_flow(message, url, lang, media_type.value)
        return


# ==================== VIDEO FLOW ====================

async def _handle_video_flow(
    message: Message, state: FSMContext, url: str, media_type: str, lang: str,
) -> None:
    """Видео/клип: показываем метаданные и клавиатуру качества."""
    status = await message.answer(
        t("download.fetching_info", lang), parse_mode="HTML",
    )
    try:
        info = await downloader.get_media_info(url, media_type)
    except MusicNotSupportedError:
        await status.edit_text(t("error.music_unsupported", lang), parse_mode="HTML")
        return
    except LiveStreamError:
        await status.edit_text(t("error.live_unsupported", lang), parse_mode="HTML")
        return
    except PrivateContentError:
        await status.edit_text(t("error.closed_profile", lang), parse_mode="HTML")
        return
    except ContentUnavailableError:
        await status.edit_text(t("error.deleted", lang), parse_mode="HTML")
        return
    except Exception as e:
        logger.exception("get_media_info упал: %s", e)
        await status.edit_text(t("error.generic", lang), parse_mode="HTML")
        return

    # Плейлист (wall с несколькими видео) — перенаправляем на пост-флоу
    if info.item_count > 1:
        await status.delete()
        await _handle_post_flow(message, url, lang, "wall_post")
        return

    qualities = info.qualities or {"720": 0}
    await state.update_data(
        url=url,
        media_type=media_type,
        title=info.title,
        description=info.description,
    )
    await state.set_state(DownloadStates.choosing_quality)

    duration = format_duration(info.duration)
    uploader = info.uploader or "—"
    text = t(
        "download.info", lang,
        title=info.title[:80],
        duration=duration,
        uploader=uploader,
    )
    await status.edit_text(
        text,
        reply_markup=get_quality_keyboard(lang, qualities),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("quality_"), DownloadStates.choosing_quality)
async def on_quality_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    """Юзер выбрал качество — запускаем скачивание."""
    quality = callback.data.removeprefix("quality_")
    data = await state.get_data()
    url = data.get("url")
    media_type = data.get("media_type", "video")
    description = data.get("description", "")
    await state.clear()
    await callback.answer()
    # сразу убираем клавиатуру — защита от двойного клика
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    async with async_session() as session:
        lang = await get_user_language(session, callback.from_user.id)

    if not url:
        await callback.message.edit_text(t("error.generic", lang), parse_mode="HTML")
        return

    # кэш: (url, quality, 0)
    async with async_session() as session:
        cached = await get_cached_vk_media(session, url, quality, 0)
    if cached:
        try:
            await callback.message.edit_text(
                t("download.cached_hit", lang), parse_mode="HTML",
            )
            await callback.message.answer_video(
                video=cached.file_id,
                caption=t("download.promo", lang, bot_username=settings.bot_username),
                parse_mode="HTML",
                supports_streaming=True,
            )
            async with async_session() as session:
                await increment_download_count(session, callback.from_user.id)
            return
        except Exception as e:
            logger.warning("Кэш file_id битый, скачиваем заново: %s", e)

    await _download_and_send_video(
        callback.message, callback.from_user.id, url, media_type, quality, lang,
        description=description,
    )


async def _download_and_send_video(
    message: Message, user_id: int, url: str, media_type: str, quality: str, lang: str,
    description: str = "",
) -> None:
    """Скачать видео в заданном качестве, отправить, закэшировать file_id, почистить файлы."""
    try:
        await message.edit_text(t("download.processing", lang), parse_mode="HTML")
    except Exception:
        pass

    downloaded_path: str | None = None
    item = None
    split_dir: str | None = None
    split_parts: list[str] = []

    # Прогресс-бар — yt-dlp вызывает хук из рабочего потока, шедулим edit в event loop.
    last_progress = {"t": 0.0}
    loop = asyncio.get_event_loop()

    def on_progress(dl_mb: float, total_mb: float, percent: int) -> None:
        now = time.time()
        if now - last_progress["t"] < PROGRESS_UPDATE_INTERVAL:
            return
        last_progress["t"] = now
        text = _make_progress_bar(lang, percent, dl_mb, total_mb)
        try:
            asyncio.run_coroutine_threadsafe(_safe_edit(message, text), loop)
        except Exception:
            pass

    try:
        item = await downloader.download_video(url, quality, progress_callback=on_progress)
        downloaded_path = item.file_path

        size = os.path.getsize(downloaded_path)
        # автосплит если файл крупнее лимита
        if size > int(1.9 * 1024 * 1024 * 1024):
            try:
                await message.edit_text(t("download.splitting", lang), parse_mode="HTML")
            except Exception:
                pass
            # сплит в отдельную поддиректорию — чтобы артефакты не оставались в work_dir видео
            split_dir = tempfile.mkdtemp(prefix="vk_split_")
            split_parts = await split_video(downloaded_path, split_dir)
            # если сплит не смог — тот же путь вернётся; обработаем ниже
            if split_parts and split_parts != [downloaded_path]:
                await _send_split_parts(
                    message, user_id, split_parts, item, url, quality, lang,
                )
                return
            # сплит не помог — отправим как есть, Telegram отклонит сам
        try:
            await message.edit_text(t("download.uploading", lang), parse_mode="HTML")
        except Exception:
            pass

        video_file = FSInputFile(downloaded_path)
        sent = await message.answer_video(
            video=video_file,
            caption=_caption_for_video(item.title, lang, description=description),
            parse_mode="HTML",
            duration=item.duration or None,
            width=item.width or None,
            height=item.height or None,
            supports_streaming=True,
        )

        try:
            await message.delete()
        except Exception:
            pass

        # кэшируем file_id (разное поле в зависимости от типа ответа Telegram)
        if sent.video:
            async with async_session() as session:
                await save_vk_media(
                    session, url, quality, sent.video.file_id, "video", 0,
                )
        async with async_session() as session:
            await increment_download_count(session, user_id)

    except FileTooLargeError:
        await message.answer(
            t("error.too_large_try_lower", lang),
            parse_mode="HTML",
        )
    except PrivateContentError:
        await message.answer(t("error.closed_profile", lang), parse_mode="HTML")
    except ContentUnavailableError:
        await message.answer(t("error.deleted", lang), parse_mode="HTML")
    except MusicNotSupportedError:
        await message.answer(t("error.music_unsupported", lang), parse_mode="HTML")
    except VkDownloadError as e:
        logger.warning("VkDownloadError: %s", e)
        await message.answer(t("error.generic", lang), parse_mode="HTML")
    except Exception as e:
        logger.exception("download_video: непредвиденная ошибка: %s", e)
        await message.answer(t("error.generic", lang), parse_mode="HTML")
    finally:
        # чистим work_dir видео (содержит исходник) и split_dir целиком
        if item and getattr(item, "work_dir", None):
            try:
                shutil.rmtree(item.work_dir, ignore_errors=True)
            except Exception:
                pass
        elif downloaded_path:
            _safe_unlink(downloaded_path)
        if split_dir:
            try:
                shutil.rmtree(split_dir, ignore_errors=True)
            except Exception:
                pass


async def _send_split_parts(
    message: Message, user_id: int, parts: list[str], item,
    url: str, quality: str, lang: str,
) -> None:
    """Отправить части большого видео. Кэш не сохраняем (много file_id, смысла нет)."""
    total = len(parts)
    for i, part_path in enumerate(parts, start=1):
        caption = t("download.part_caption", lang, n=i, total=total)
        try:
            await message.answer_video(
                video=FSInputFile(part_path),
                caption=caption,
                parse_mode="HTML",
                supports_streaming=True,
            )
        except Exception as e:
            logger.warning("Не удалось отправить часть %d: %s", i, e)

    try:
        await message.delete()
    except Exception:
        pass

    async with async_session() as session:
        await increment_download_count(session, user_id)


_GENERIC_TITLE_RE = __import__("re").compile(
    r"^(clip|video|wall\s*post|post|story|vk)\s+(by|from|от|у|с)\s+.*$",
    __import__("re").IGNORECASE,
)


def _caption_for_video(title: str, lang: str, description: str = "") -> str:
    """Подпись к видео: описание под постом, иначе title (если не шаблонный),
    иначе i18n-фолбэк для текущего языка. Всегда + промо бота.
    """
    promo = t("download.promo", lang, bot_username=settings.bot_username)
    desc = (description or "").strip()
    safe_title = (title or "").strip()

    body = ""
    if desc:
        body = _escape_html(desc[:900])
    elif safe_title and not _GENERIC_TITLE_RE.match(safe_title):
        body = f"<b>{_escape_html(safe_title[:200])}</b>"
    else:
        body = t("download.no_caption", lang)

    if body:
        return f"{body}{promo}"
    return promo.lstrip()


def _escape_html(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


POST_TEXT_LIMIT = 800


async def _send_long_text(message: Message, text: str, url: str, lang: str) -> None:
    """Отправить текст поста отдельным сообщением.

    Если текст длиннее POST_TEXT_LIMIT — обрезаем, ставим «...» и добавляем
    ссылку «дочитать в VK». HTML-escaped.
    """
    raw = text.strip()
    if not raw:
        return
    if len(raw) > POST_TEXT_LIMIT:
        safe = _escape_html(raw[:POST_TEXT_LIMIT].rstrip()) + "..."
        safe += "\n\n" + t("download.read_more", lang, url=_escape_html(url))
    else:
        safe = _escape_html(raw)
    try:
        await message.answer(safe, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        logger.warning("Не удалось отправить текст поста: %s", e)


# ==================== DOC FLOW ====================

async def _handle_doc_flow(message: Message, url: str, lang: str) -> None:
    """Документ VK (GIF/mp3/файл)."""
    status = await message.answer(t("download.processing", lang), parse_mode="HTML")

    # кэш
    async with async_session() as session:
        cached = await get_cached_vk_media(session, url, "doc", 0)
    if cached:
        try:
            await status.edit_text(t("download.cached_hit", lang), parse_mode="HTML")
            await _send_cached(message, cached.file_id, cached.media_type, lang)
            async with async_session() as session:
                await increment_download_count(session, message.from_user.id)
            return
        except Exception as e:
            logger.warning("Кэш doc битый: %s", e)

    file_path: str | None = None
    doc_item = None

    last_progress = {"t": 0.0}
    loop = asyncio.get_event_loop()

    def on_progress(dl_mb: float, total_mb: float, percent: int) -> None:
        now = time.time()
        if now - last_progress["t"] < PROGRESS_UPDATE_INTERVAL:
            return
        last_progress["t"] = now
        text = _make_progress_bar(lang, percent, dl_mb, total_mb)
        try:
            asyncio.run_coroutine_threadsafe(_safe_edit(status, text), loop)
        except Exception:
            pass

    try:
        doc_item = await downloader.download_doc(url, progress_callback=on_progress)
        item = doc_item
        file_path = item.file_path

        sent = None
        if item.media_type == "animation":
            sent = await message.answer_animation(
                animation=FSInputFile(file_path),
                caption=t("download.promo", lang, bot_username=settings.bot_username),
                parse_mode="HTML",
            )
            file_id = sent.animation.file_id if sent.animation else None
        elif item.media_type == "audio":
            sent = await message.answer_audio(
                audio=FSInputFile(file_path),
                caption=t("download.promo", lang, bot_username=settings.bot_username),
                parse_mode="HTML",
            )
            file_id = sent.audio.file_id if sent.audio else None
        else:
            sent = await message.answer_document(
                document=FSInputFile(file_path),
                caption=t("download.promo", lang, bot_username=settings.bot_username),
                parse_mode="HTML",
            )
            file_id = sent.document.file_id if sent.document else None

        try:
            await status.delete()
        except Exception:
            pass

        if file_id:
            async with async_session() as session:
                await save_vk_media(
                    session, url, "doc", file_id, item.media_type, 0,
                )
        async with async_session() as session:
            await increment_download_count(session, message.from_user.id)

    except FileTooLargeError:
        await status.edit_text(t("error.too_large", lang), parse_mode="HTML")
    except PrivateContentError:
        await status.edit_text(t("error.closed_profile", lang), parse_mode="HTML")
    except ContentUnavailableError:
        await status.edit_text(t("error.deleted", lang), parse_mode="HTML")
    except Exception as e:
        logger.exception("download_doc упал: %s", e)
        await status.edit_text(t("error.generic", lang), parse_mode="HTML")
    finally:
        if doc_item and getattr(doc_item, "work_dir", None):
            try:
                shutil.rmtree(doc_item.work_dir, ignore_errors=True)
            except Exception:
                pass
        elif file_path:
            _safe_unlink(file_path)


# ==================== PHOTO / STORY FLOW ====================

async def _handle_photo_flow(
    message: Message, url: str, lang: str, quality_key: str,
) -> None:
    """Одиночное фото или сторис. quality_key: "photo" или "story"."""
    status = await message.answer(t("download.processing", lang), parse_mode="HTML")

    # кэш одиночного фото
    async with async_session() as session:
        cached = await get_cached_vk_media(session, url, quality_key, 0)
    if cached:
        try:
            await status.edit_text(t("download.cached_hit", lang), parse_mode="HTML")
            await _send_cached(message, cached.file_id, cached.media_type, lang)
            async with async_session() as session:
                await increment_download_count(session, message.from_user.id)
            return
        except Exception:
            pass

    work_dir: str | None = None
    try:
        items = await downloader.download_photo(url)
        if items:
            work_dir = items[0].work_dir

        if not items:
            await status.edit_text(t("error.deleted", lang), parse_mode="HTML")
            return

        # Текст описания под фото/историей (если есть) — отдельным сообщением до медиа.
        post_text = ""
        try:
            post_text = await downloader.get_post_text(url)
        except Exception as e:
            logger.debug("get_post_text для photo/story упал: %s", e)
        if post_text:
            await _send_long_text(message, post_text, url, lang)

        # Если всё-таки скачалось несколько файлов (сторис = карусель) — отправим альбомом
        if len(items) == 1:
            it = items[0]
            sent = await _send_single_media(message, it, lang)
            file_id = _extract_file_id(sent, it.media_type)
            try:
                await status.delete()
            except Exception:
                pass
            if file_id:
                async with async_session() as session:
                    await save_vk_media(
                        session, url, quality_key, file_id, it.media_type, 0,
                    )
        else:
            # несколько файлов — сохраняем под тем же quality_key, что читали выше
            await _send_as_media_groups(message, items, lang, url, cache_prefix=quality_key)
            try:
                await status.delete()
            except Exception:
                pass

        async with async_session() as session:
            await increment_download_count(session, message.from_user.id)

    except FileTooLargeError:
        await status.edit_text(t("error.too_large", lang), parse_mode="HTML")
    except PrivateContentError:
        await status.edit_text(t("error.closed_profile", lang), parse_mode="HTML")
    except ContentUnavailableError:
        await status.edit_text(t("error.deleted", lang), parse_mode="HTML")
    except Exception as e:
        logger.exception("download_photo упал: %s", e)
        await status.edit_text(t("error.generic", lang), parse_mode="HTML")
    finally:
        if work_dir:
            try:
                shutil.rmtree(work_dir, ignore_errors=True)
            except Exception:
                pass


# ==================== ALBUM / WALL POST FLOW ====================

async def _handle_post_flow(
    message: Message, url: str, lang: str, media_type: str,
) -> None:
    """Альбом или пост со стены — пачка медиа, отправляется media group'ами по 10."""
    status = await message.answer(t("download.processing", lang), parse_mode="HTML")

    # кэш: все элементы поста должны быть целы
    async with async_session() as session:
        cached_items = await get_cached_vk_post(session, url)
    if cached_items:
        try:
            await status.edit_text(t("download.cached_hit", lang), parse_mode="HTML")
            await _send_cached_post(message, cached_items, lang)
            async with async_session() as session:
                await increment_download_count(session, message.from_user.id)
            return
        except Exception as e:
            logger.warning("Кэш поста битый: %s", e)

    work_dir: str | None = None
    try:
        items = await downloader.download_post_attachments(url)
        if items:
            work_dir = items[0].work_dir
        if not items:
            await status.edit_text(t("error.deleted", lang), parse_mode="HTML")
            return

        # Текст поста отправляем ОТДЕЛЬНЫМ сообщением перед media group.
        # Так не упираемся в лимит caption=1024 и юзер видит полный текст.
        post_text = ""
        try:
            post_text = await downloader.get_post_text(url)
        except Exception as e:
            logger.debug("не удалось достать текст поста: %s", e)

        if post_text:
            await _send_long_text(message, post_text, url, lang)

        await _send_as_media_groups(
            message, items, lang, url, cache_prefix="post",
        )
        try:
            await status.delete()
        except Exception:
            pass

        async with async_session() as session:
            await increment_download_count(session, message.from_user.id)

    except FileTooLargeError:
        await status.edit_text(t("error.too_large", lang), parse_mode="HTML")
    except PrivateContentError:
        await status.edit_text(t("error.closed_profile", lang), parse_mode="HTML")
    except ContentUnavailableError:
        await status.edit_text(t("error.deleted", lang), parse_mode="HTML")
    except Exception as e:
        logger.exception("download_post упал: %s", e)
        await status.edit_text(t("error.generic", lang), parse_mode="HTML")
    finally:
        if work_dir:
            try:
                shutil.rmtree(work_dir, ignore_errors=True)
            except Exception:
                pass


# ==================== HELPERS ====================

async def _send_single_media(message: Message, item, lang: str) -> Message:
    """Отправить одно вложение правильным методом. Возвращает отправленное сообщение."""
    caption = t("download.promo", lang, bot_username=settings.bot_username)
    if item.media_type == "photo":
        return await message.answer_photo(
            photo=FSInputFile(item.file_path),
            caption=caption,
            parse_mode="HTML",
        )
    if item.media_type == "video":
        return await message.answer_video(
            video=FSInputFile(item.file_path),
            caption=caption,
            parse_mode="HTML",
            supports_streaming=True,
        )
    if item.media_type == "animation":
        return await message.answer_animation(
            animation=FSInputFile(item.file_path),
            caption=caption,
            parse_mode="HTML",
        )
    if item.media_type == "audio":
        return await message.answer_audio(
            audio=FSInputFile(item.file_path),
            caption=caption,
            parse_mode="HTML",
        )
    return await message.answer_document(
        document=FSInputFile(item.file_path),
        caption=caption,
        parse_mode="HTML",
    )


def _extract_file_id(sent: Message, media_type: str) -> str | None:
    if media_type == "photo" and sent.photo:
        return sent.photo[-1].file_id
    if media_type == "video" and sent.video:
        return sent.video.file_id
    if media_type == "animation" and sent.animation:
        return sent.animation.file_id
    if media_type == "audio" and sent.audio:
        return sent.audio.file_id
    if sent.document:
        return sent.document.file_id
    return None


async def _send_as_media_groups(
    message: Message, items, lang: str, url: str, cache_prefix: str,
) -> None:
    """Разбить список items на пачки по 10, отправить send_media_group.

    Только photo + video идут в media group (Telegram требование).
    Documents / animations / audio — отдельными сообщениями после.
    Кэшируем file_id каждого элемента по item_index.

    Промо-подпись бота ставится на первое медиа каждой media group
    и под каждым standalone-медиа.
    """
    promo = t("download.promo", lang, bot_username=settings.bot_username)

    group_items: list = []
    standalone: list = []
    for it in items:
        if it.media_type in ("photo", "video"):
            group_items.append(it)
        else:
            standalone.append(it)

    global_idx = 0
    # отправка media group'ами по 10
    for chunk_start in range(0, len(group_items), 10):
        chunk = group_items[chunk_start:chunk_start + 10]
        media_inputs = []
        for i, it in enumerate(chunk):
            caption = None
            if i == 0:
                caption = promo.lstrip()
            if it.media_type == "photo":
                media_inputs.append(InputMediaPhoto(
                    media=FSInputFile(it.file_path),
                    caption=caption,
                    parse_mode="HTML" if caption else None,
                ))
            else:
                media_inputs.append(InputMediaVideo(
                    media=FSInputFile(it.file_path),
                    caption=caption,
                    parse_mode="HTML" if caption else None,
                    supports_streaming=True,
                ))

        try:
            sent_list = await message.answer_media_group(media=media_inputs)
        except Exception as e:
            logger.warning("send_media_group упал, шлём поштучно: %s", e)
            sent_list = []
            for it in chunk:
                try:
                    sent = await _send_single_media(message, it, lang)
                    sent_list.append(sent)
                except Exception as e2:
                    logger.warning("fallback send одного медиа упал: %s", e2)
                    sent_list.append(None)

        # кэшируем file_id чанка
        for it, sent in zip(chunk, sent_list):
            if sent is None:
                global_idx += 1
                continue
            file_id = _extract_file_id(sent, it.media_type)
            if file_id:
                try:
                    async with async_session() as session:
                        await save_vk_media(
                            session, url, cache_prefix, file_id, it.media_type, global_idx,
                            item_count=len(items),
                        )
                except Exception as e:
                    logger.warning("save_vk_media failed: %s", e)
            global_idx += 1

    # отдельные медиа (не входящие в media group)
    for it in standalone:
        try:
            sent = await _send_single_media(message, it, lang)
        except Exception as e:
            logger.warning("send standalone упал: %s", e)
            global_idx += 1
            continue
        file_id = _extract_file_id(sent, it.media_type)
        if file_id:
            try:
                async with async_session() as session:
                    await save_vk_media(
                        session, url, cache_prefix, file_id, it.media_type, global_idx,
                    )
            except Exception as e:
                logger.warning("save_vk_media failed: %s", e)
        global_idx += 1


async def _send_cached(message: Message, file_id: str, media_type: str, lang: str) -> None:
    """Отправить по file_id из кэша."""
    caption = t("download.promo", lang, bot_username=settings.bot_username)
    if media_type == "photo":
        await message.answer_photo(photo=file_id, caption=caption, parse_mode="HTML")
    elif media_type == "video":
        await message.answer_video(video=file_id, caption=caption, parse_mode="HTML", supports_streaming=True)
    elif media_type == "animation":
        await message.answer_animation(animation=file_id, caption=caption, parse_mode="HTML")
    elif media_type == "audio":
        await message.answer_audio(audio=file_id, caption=caption, parse_mode="HTML")
    else:
        await message.answer_document(document=file_id, caption=caption, parse_mode="HTML")


async def _send_cached_post(
    message: Message, entries, lang: str,
) -> None:
    """Отправить кэш поста. entries отсортированы по item_index."""
    # группируем только photo+video для media group
    group_slots = []
    standalone = []
    for e in entries:
        if e.media_type in ("photo", "video"):
            group_slots.append(e)
        else:
            standalone.append(e)

    promo = t("download.promo", lang, bot_username=settings.bot_username)
    for chunk_start in range(0, len(group_slots), 10):
        chunk = group_slots[chunk_start:chunk_start + 10]
        media_inputs = []
        for i, e in enumerate(chunk):
            caption = None
            if i == 0:
                caption = promo.lstrip()
            if e.media_type == "photo":
                media_inputs.append(InputMediaPhoto(
                    media=e.file_id, caption=caption,
                    parse_mode="HTML" if caption else None,
                ))
            else:
                media_inputs.append(InputMediaVideo(
                    media=e.file_id, caption=caption,
                    parse_mode="HTML" if caption else None,
                    supports_streaming=True,
                ))
        await message.answer_media_group(media=media_inputs)

    for e in standalone:
        await _send_cached(message, e.file_id, e.media_type, lang)


def _safe_unlink(path: str) -> None:
    """Безопасно удалить файл (never raise)."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError as e:
        logger.warning("Не удалось удалить файл %s: %s", path, e)
