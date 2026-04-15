"""Сервис скачивания медиа из ВКонтакте.

Движки:
  * yt-dlp — primary для video / clip / video_ext / wall (playlist) / doc (GIF, mp3, файлы).
  * gallery-dl — fallback и основной для photo / album (yt-dlp не умеет фото VK).

Fallback-цепочка (для всех публичных URL):
  1) primary (без прокси, без cookies — VK в РФ доступен)
  2) proxy (если settings.proxy_url задан — для не-РФ IP при гео-блоке)
  3) cookies (если cookies.txt есть — для 18+/закрытых/сторис)
  4) proxy + cookies

Музыка ВК (audio_*): официально скачивание Audio API заблокировано без специальных
токенов мобильных клиентов. yt-dlp VK extractor аудио не поддерживает. Возвращаем
MusicNotSupportedError и даём юзеру осмысленный текст в хендлере.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from typing import Callable

from bot.config import settings

logger = logging.getLogger(__name__)

# Лимит Telegram Local Bot API — 2 ГБ. Под это же settings.max_file_size.
MAX_FILE_SIZE = settings.max_file_size

# Семафор — одновременно не больше N скачиваний (защита от OOM/диск).
_DOWNLOAD_SEMAPHORE = asyncio.Semaphore(3)

# Префлайт — скрываем качества крупнее этого лимита (МБ).
MAX_QUALITY_SIZE_MB = int(MAX_FILE_SIZE / 1024 / 1024)  # == 2048

# Максимум файлов из одного альбома/поста — защита от гигантских альбомов.
MAX_ALBUM_ITEMS = 50


class VkDownloadError(Exception):
    """Базовая ошибка VK-скачивалки."""


class FileTooLargeError(VkDownloadError):
    """Файл превышает лимит Telegram."""


class MusicNotSupportedError(VkDownloadError):
    """Музыка VK не поддерживается (заблокирована аудио API)."""


class PrivateContentError(VkDownloadError):
    """Контент приватный / закрытый профиль."""


class ContentUnavailableError(VkDownloadError):
    """Удалено / гео-блок / недоступно."""


class LiveStreamError(VkDownloadError):
    """Это прямой эфир в реальном времени — не скачиваем."""


@dataclass
class VkMediaInfo:
    """Метаданные медиа до скачивания."""
    media_type: str                 # "video" / "clip" / "photo" / "album" / "wall_post" / "doc" / "story"
    title: str = ""
    description: str = ""
    duration: int = 0
    uploader: str | None = None
    thumbnail: str | None = None
    # для видео: {"360": 45, "720": 120, "1080": 280} — (квалити → примерный размер в МБ)
    qualities: dict[str, int] = field(default_factory=dict)
    # для альбомов/постов с несколькими вложениями
    item_count: int = 1
    # список вложений поста (для wall_post): [{"type": "photo"|"video"|"doc", "url": ...}, ...]
    attachments: list[dict] = field(default_factory=list)


@dataclass
class DownloadedItem:
    """Один скачанный файл (элемент поста или одиночный медиа)."""
    file_path: str
    media_type: str   # "video" / "photo" / "audio" / "document" / "animation"
    title: str = ""
    duration: int | None = None
    width: int | None = None
    height: int | None = None
    # рабочая поддиректория — хендлер должен удалить её через shutil.rmtree в finally
    work_dir: str | None = None


ProgressCallback = Callable[[float, float, int], None] | None


_QUALITY_LADDER = [144, 240, 360, 480, 720, 1080, 1440, 2160]


def _snap_to_ladder(value: int) -> int:
    """Привязать произвольный height/width к ближайшей стандартной ступени качества."""
    if not value:
        return 0
    # точное совпадение
    if value in _QUALITY_LADDER:
        return value
    # ближайшая ступень при отклонении ≤60 пикселей (854→480, 426→240 и т.п.)
    best = min(_QUALITY_LADDER, key=lambda s: abs(s - value))
    if abs(best - value) <= 60:
        return best
    # если сильно выше 1080 — возвращаем как есть (на случай экзотики)
    return value


def classify_error(exc: BaseException | str) -> str:
    """Классифицирует ошибку yt-dlp/gallery-dl/сети в категорию.

    Категории:
      - 'private'          — закрытый профиль / приват
      - 'not_found'        — удалено / 404
      - 'geo_blocked'      — гео-блок / недоступно в регионе
      - 'music_unsupported' — запрос на аудио VK
      - 'network'          — таймауты / соединение
      - 'cookies_expired'  — cookies протухли / требует логин
      - 'too_large'        — размер превышен
      - 'unknown'          — всё прочее
    """
    if isinstance(exc, MusicNotSupportedError):
        return "music_unsupported"
    if isinstance(exc, LiveStreamError):
        return "live"
    if isinstance(exc, PrivateContentError):
        return "private"
    if isinstance(exc, ContentUnavailableError):
        return "not_found"
    if isinstance(exc, FileTooLargeError):
        return "too_large"

    msg = str(exc).lower()
    # строгие фразы закрытого профиля (не ловим обычное слово "доступ" без контекста)
    if (
        "private profile" in msg
        or "private video" in msg
        or "access denied" in msg
        or "this video is only available for friends" in msg
        or "only available to signed-in users" in msg
        or "available to signed-in" in msg
        or "only available for signed-in" in msg
        or "login is required" in msg
        or "доступ запрещ" in msg
        or "закрытый профиль" in msg
        or "нет доступа" in msg
        or "только для авторизованных" in msg
    ):
        return "private"
    if "not found" in msg or "removed" in msg or "удалено" in msg or "404" in msg or "video was deleted" in msg:
        return "not_found"
    if "geo" in msg or "region" in msg or "country" in msg or "not available in your" in msg:
        return "geo_blocked"
    # строго: музыка VK заблокирована — совпадение конкретных фраз
    if (
        "vk audio" in msg
        or "audio_unsupported" in msg
        or "audio extraction is not supported" in msg
        or "vkaudio" in msg
    ):
        return "music_unsupported"
    if "login" in msg and "required" in msg:
        return "cookies_expired"
    if "cookies" in msg:
        return "cookies_expired"
    if "timeout" in msg or "timed out" in msg or "connection" in msg or "unreachable" in msg:
        return "network"
    # Кривой URL (битый домен, невалидный idna, unsupported extractor) — сразу останавливаемся,
    # нет смысла тянуть через proxy/WARP то, что yt-dlp даже распарсить не может.
    if (
        "label empty" in msg
        or "label too long" in msg
        or "idna" in msg
        or "unsupported url" in msg
        or "no suitable extractor" in msg
        or "invalid url" in msg
    ):
        return "bad_url"
    return "unknown"


class VkDownloader:
    """Скачивалка VK-медиа. Тонкая обёртка над yt-dlp и gallery-dl."""

    _COOKIES_PATH = "/app/cookies/cookies.txt"
    # WARP — контейнер docker-warp-socks (см. docker-compose.yml) на порту 9091.
    # VPS в Германии часто имеет заблокированный VK-серверный IP → WARP выдаёт
    # клиентский IP Cloudflare.
    WARP_PROXY = "socks5://warp:9091"

    def __init__(self) -> None:
        self.download_dir = tempfile.mkdtemp(prefix="vk_bot_")
        self._proxy = getattr(settings, "proxy_url", None) or os.environ.get("PROXY_URL") or None
        self.on_source_failed: Callable[[str, str], None] | None = None

        if self._proxy:
            logger.info("VK: резидентный прокси: %s", self._proxy)
        else:
            logger.info("VK: резидентный прокси не задан")
        logger.info("VK: WARP fallback: %s", self.WARP_PROXY)

        if self.has_cookies():
            logger.info("VK: cookies.txt найдены (fallback для 18+/приватного)")

    # ================ PUBLIC API ================

    def has_cookies(self) -> bool:
        return os.path.isfile(self._COOKIES_PATH)

    async def get_media_info(self, url: str, media_type: str) -> VkMediaInfo:
        """Получить метаданные медиа (без скачивания файла).

        Для video/clip/video_ext — через yt-dlp (возвращает форматы).
        Для wall_post — yt-dlp вернёт либо видео, либо playlist, либо ничего —
          тогда парсим через gallery-dl (пост с фото).
        Для photo/album/story — gallery-dl info-режим.
        """
        async with _DOWNLOAD_SEMAPHORE:
            if media_type in ("video", "clip", "video_ext"):
                return await self._ytdlp_info(url, media_type)
            if media_type == "doc":
                return await self._ytdlp_info(url, media_type)
            if media_type == "wall_post":
                # сначала пробуем yt-dlp (если в посте есть видео — вернёт playlist/entry)
                try:
                    info = await self._ytdlp_info(url, media_type)
                    if info.item_count > 0:
                        return info
                except Exception as e:
                    logger.debug("yt-dlp на wall_post упал, пробуем gallery-dl: %s", e)
                return await self._gallerydl_info(url, media_type)
            if media_type in ("photo", "album", "story"):
                return await self._gallerydl_info(url, media_type)

            # channel / unknown — не поддерживаем явно
            raise VkDownloadError(f"unsupported_media_type: {media_type}")

    async def download_video(
        self,
        url: str,
        quality: str,
        progress_callback: ProgressCallback = None,
    ) -> DownloadedItem:
        """Скачать одиночное видео/клип/video_ext в указанном качестве."""
        async with _DOWNLOAD_SEMAPHORE:
            return await self._ytdlp_download_video(url, quality, progress_callback)

    async def download_doc(
        self, url: str, progress_callback: ProgressCallback = None,
    ) -> DownloadedItem:
        """Скачать документ (doc — GIF, mp3, файл)."""
        async with _DOWNLOAD_SEMAPHORE:
            return await self._ytdlp_download_doc(url, progress_callback)

    async def download_photo(self, url: str) -> list[DownloadedItem]:
        """Скачать одно фото или все фото альбома/поста — возвращает список файлов.
        Для single photo список длины 1. Для album/post — все фотографии.
        """
        async with _DOWNLOAD_SEMAPHORE:
            return await self._gallerydl_download(url)

    async def download_post_attachments(self, url: str) -> list[DownloadedItem]:
        """Скачать все вложения поста со стены: фото + видео (мелкие) + документы.

        Используем gallery-dl — он умеет parsить wall-посты VK и вытаскивать
        все attachments, включая ссылки на видео/документы.
        """
        async with _DOWNLOAD_SEMAPHORE:
            return await self._gallerydl_download(url)

    async def get_post_text(self, url: str) -> str:
        """Достать текст поста из метаданных gallery-dl (поля text / description /
        caption / content / post_text). Если текста нет — возвращаем пустую
        строку, без HTML-скрэйпа и догадок. Ошибки мягкие.
        """
        candidates: list[str] = []
        for name, extra_args in self._gallerydl_attempts():
            try:
                items = await self._run_gallerydl_simulate(url, extra_args)
                for it in items:
                    for key in ("text", "description", "caption", "content", "post_text"):
                        v = it.get(key)
                        if v and isinstance(v, str):
                            candidates.append(v.strip())
                if candidates:
                    break
            except Exception as e:
                logger.debug("get_post_text [%s] упал: %s", name, e)
                continue
        if not candidates:
            return ""
        return max(candidates, key=len)

    def cleanup_file(self, path: str) -> None:
        """Удалить файл. Используется после отправки — и при ошибке тоже."""
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except OSError as e:
            logger.warning("VK: не удалось удалить %s: %s", path, e)

    def cleanup_dir(self, path: str) -> None:
        """Удалить директорию рекурсивно (для gallery-dl output)."""
        try:
            if path and os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
        except OSError as e:
            logger.warning("VK: не удалось удалить dir %s: %s", path, e)

    # ================ INTERNALS: yt-dlp ================

    def _ydl_opts(
        self,
        use_proxy: bool = False,
        use_warp: bool = False,
        use_cookies: bool = False,
    ) -> dict:
        """Базовые опции yt-dlp. Формируются из комбинации флагов (для fallback-цепочки)."""
        opts = {
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 30,
            "retries": 3,
            # ссылка вида /playlist/-X_Y/video-X_Y?list=... — это одно видео из плейлиста;
            # noplaylist=True заставляет yt-dlp взять именно это видео, не тянуть весь список.
            "noplaylist": True,
        }
        # Порядок: резидентный прокси имеет приоритет над WARP если оба флага выставлены
        # (в fallback-цепочке они передаются раздельно, так что это условие не сработает).
        if use_proxy and self._proxy:
            opts["proxy"] = self._proxy
        elif use_warp:
            opts["proxy"] = self.WARP_PROXY
        if use_cookies and self.has_cookies():
            opts["cookiefile"] = self._COOKIES_PATH
        return opts

    def _fire_source_failed(self, source: str, error: BaseException) -> None:
        if self.on_source_failed is None:
            return
        try:
            self.on_source_failed(source, str(error))
        except Exception as e:
            logger.warning("on_source_failed callback упал: %s", e)

    async def _run_ytdlp_extract(self, url: str, opts: dict, download: bool = False) -> dict:
        """Блокирующий yt-dlp.extract_info → executor."""
        import yt_dlp

        def _blocking() -> dict:
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=download)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _blocking)

    def _fallback_configs(self, base_opts: dict) -> list[tuple[str, dict]]:
        """Собрать очередь попыток: (name, opts).

        Цепочка: primary → resident proxy → WARP → cookies → proxy+cookies → warp+cookies.
        При каждом падении уведомляем админа через _fire_source_failed.
        """
        queue: list[tuple[str, dict]] = [("primary", {**base_opts, **self._ydl_opts()})]
        if self._proxy:
            queue.append(("proxy", {**base_opts, **self._ydl_opts(use_proxy=True)}))
        queue.append(("warp", {**base_opts, **self._ydl_opts(use_warp=True)}))
        if self.has_cookies():
            queue.append(("cookies", {**base_opts, **self._ydl_opts(use_cookies=True)}))
        if self._proxy and self.has_cookies():
            queue.append(
                ("proxy+cookies", {**base_opts, **self._ydl_opts(use_proxy=True, use_cookies=True)})
            )
        if self.has_cookies():
            queue.append(
                ("warp+cookies", {**base_opts, **self._ydl_opts(use_warp=True, use_cookies=True)})
            )
        return queue

    async def _ytdlp_info(self, url: str, media_type: str) -> VkMediaInfo:
        """Метаданные через yt-dlp с fallback-цепочкой."""
        base = {
            "skip_download": True,
        }
        last_err: Exception | None = None
        for name, opts in self._fallback_configs(base):
            try:
                t0 = time.monotonic()
                info = await self._run_ytdlp_extract(url, opts, download=False)
                logger.info(
                    "[METRIC] vk get_info %.2fs source=%s type=%s url=%s",
                    time.monotonic() - t0, name, media_type, url,
                )
                return self._parse_ytdlp_info(info, media_type)
            except Exception as e:
                last_err = e
                cat = classify_error(e)
                # контентные ошибки — не пытаемся fallback'ами, пробрасываем сразу
                if cat in ("private", "not_found", "geo_blocked", "live", "music_unsupported", "bad_url"):
                    self._raise_categorized(e)
                logger.warning("yt-dlp info [%s] упал: %s", name, e)
                self._fire_source_failed(f"vk.ytdlp.{name}", e)

        # все попытки упали
        if last_err:
            self._raise_categorized(last_err)
        raise VkDownloadError("get_info_failed")

    def _parse_ytdlp_info(self, info: dict, media_type: str) -> VkMediaInfo:
        # yt-dlp на playlist вернёт entries
        entries = info.get("entries")
        if entries is not None:
            items = [e for e in entries if e]
            # для video/clip/video_ext — ссылка на одно видео внутри плейлиста,
            # берём первое (или единственное) и парсим как одиночное.
            if media_type in ("video", "clip", "video_ext") and items:
                info = items[0]
                # провалимся дальше в single-item парсинг ниже
            else:
                # wall_post / unknown — отдаём как playlist, дальше скачает gallery-dl
                return VkMediaInfo(
                    media_type=media_type,
                    title=info.get("title") or "VK пост",
                    item_count=len(items),
                    attachments=[
                        {"type": "video", "url": e.get("webpage_url") or e.get("url"),
                         "title": e.get("title", "")}
                        for e in items
                    ],
                )

        # Детект live-стрима: VK помечает их is_live=True / live_status='is_live'.
        # Прямые эфиры не скачиваем (см. ТЗ: записи эфиров — ок, live — нет).
        if info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming"):
            raise LiveStreamError("live_stream_not_supported")

        qualities = self._parse_qualities(info)
        if not qualities and not (info.get("formats") or []):
            # у yt-dlp вообще не вышло вытащить форматы — контент недоступен
            raise ContentUnavailableError("no_formats_available")
        return VkMediaInfo(
            media_type=media_type,
            title=info.get("title") or "VK Видео",
            description=(info.get("description") or "").strip(),
            duration=int(info.get("duration") or 0),
            uploader=info.get("uploader") or info.get("channel"),
            thumbnail=info.get("thumbnail"),
            qualities=qualities,
            item_count=1,
        )

    def _parse_qualities(self, info: dict) -> dict[str, int]:
        """Построить {quality: size_mb} из форматов yt-dlp. Скрываем > MAX_QUALITY_SIZE_MB.

        Для вертикальных клипов yt-dlp возвращает height = ширина кадра (например
        426/640/852) — берём min(width, height), это "короткая сторона" и она
        совпадает со стандартной лестницей 240/360/480/720/1080 и для ландшафта,
        и для вертикали.
        """
        formats = info.get("formats") or []
        duration = info.get("duration") or 0
        result: dict[str, int] = {}
        for fmt in formats:
            h = fmt.get("height") or 0
            w = fmt.get("width") or 0
            if not h and not w:
                continue
            short = min(h, w) if (h and w) else (h or w)
            short = _snap_to_ladder(short)
            if not short:
                continue
            size = fmt.get("filesize") or fmt.get("filesize_approx") or 0
            if not size and fmt.get("tbr") and duration:
                size = int(fmt["tbr"] * 1000 / 8 * duration)
            size_mb = max(int(size / 1024 / 1024), 0) if size else 0
            key = str(short)
            prev = result.get(key, 0)
            if size_mb > prev:
                result[key] = size_mb

        # префлайт-фильтр — отрезаем качества > лимита
        filtered = {k: v for k, v in result.items() if v == 0 or v <= MAX_QUALITY_SIZE_MB}
        return filtered or result

    async def _ytdlp_download_video(
        self, url: str, quality: str, progress_callback: ProgressCallback,
    ) -> DownloadedItem:
        """Скачивание видео в заданном качестве с fallback.

        Каждый вызов создаёт СВОЮ поддиректорию — это защищает от race condition
        между юзерами (не найдём чужой файл по mtime).
        """
        subdir = tempfile.mkdtemp(prefix="ytv_", dir=self.download_dir)
        output_template = os.path.join(subdir, f"%(id)s_{quality}p.%(ext)s")
        try:
            height = int(quality)
        except ValueError:
            height = 720
        # Предпочитаем h264 (avc1) + aac в mp4 — иначе Telegram показывает
        # чёрное окно со звуком для VP9/AV1-потоков VK.
        format_str = (
            f"bestvideo[height<={height}][vcodec^=avc1]+bestaudio[acodec^=mp4a]/"
            f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/"
            f"best[height<={height}][ext=mp4][vcodec^=avc1]/"
            f"best[height<={height}][ext=mp4]/"
            f"best[height<={height}]/"
            f"best"
        )
        base = {
            "format": format_str,
            "outtmpl": output_template,
            "merge_output_format": "mp4",
            # faststart для корректного воспроизведения в Telegram без перемотки в конец
            "postprocessor_args": {"ffmpeg": ["-movflags", "+faststart"]},
        }
        if progress_callback:
            self._attach_progress_hook(base, progress_callback)

        last_err: Exception | None = None
        t0 = time.monotonic()
        try:
            for name, opts in self._fallback_configs(base):
                try:
                    info = await self._run_ytdlp_extract(url, opts, download=True)
                    file_path = self._find_downloaded_file_in(info, subdir)
                    if not file_path or not os.path.exists(file_path):
                        raise VkDownloadError("downloaded_file_missing")
                    size = os.path.getsize(file_path)
                    if size > MAX_FILE_SIZE * 1.5:
                        # совсем огромный — чистим и жалуемся, автосплит лишь до 2*MAX
                        self.cleanup_dir(subdir)
                        raise FileTooLargeError(f"file {size} bytes")
                    logger.info(
                        "[METRIC] vk download_video %.2fs source=%s q=%s size=%.1fMB",
                        time.monotonic() - t0, name, quality, size / 1024 / 1024,
                    )
                    return DownloadedItem(
                        file_path=file_path,
                        media_type="video",
                        title=info.get("title", "VK Видео"),
                        duration=info.get("duration"),
                        width=info.get("width"),
                        height=info.get("height"),
                        work_dir=subdir,
                    )
                except FileTooLargeError:
                    raise
                except Exception as e:
                    last_err = e
                    cat = classify_error(e)
                    if cat in ("private", "not_found", "geo_blocked", "live", "music_unsupported", "bad_url"):
                        self._raise_categorized(e)
                    logger.warning("yt-dlp download [%s] упал: %s", name, e)
                    self._fire_source_failed(f"vk.ytdlp.{name}", e)

            if last_err:
                self._raise_categorized(last_err)
            raise VkDownloadError("download_failed")
        except BaseException:
            # любая ошибка → чистим subdir
            self.cleanup_dir(subdir)
            raise

    async def _ytdlp_download_doc(
        self, url: str, progress_callback: ProgressCallback,
    ) -> DownloadedItem:
        """Скачать документ VK (GIF, mp3, произвольный файл). subdir per-call."""
        subdir = tempfile.mkdtemp(prefix="ytd_", dir=self.download_dir)
        output_template = os.path.join(subdir, "%(id)s_doc.%(ext)s")
        base = {
            "format": "best",
            "outtmpl": output_template,
        }
        if progress_callback:
            self._attach_progress_hook(base, progress_callback)

        last_err: Exception | None = None
        try:
            for name, opts in self._fallback_configs(base):
                try:
                    info = await self._run_ytdlp_extract(url, opts, download=True)
                    file_path = self._find_downloaded_file_in(info, subdir)
                    if not file_path:
                        raise VkDownloadError("downloaded_file_missing")
                    if os.path.getsize(file_path) > MAX_FILE_SIZE:
                        self.cleanup_dir(subdir)
                        raise FileTooLargeError("doc_too_large")
                    ext = os.path.splitext(file_path)[1].lower()
                    media_type = "animation" if ext == ".gif" else (
                        "audio" if ext in (".mp3", ".m4a", ".ogg", ".opus") else "document"
                    )
                    return DownloadedItem(
                        file_path=file_path,
                        media_type=media_type,
                        title=info.get("title", ""),
                        work_dir=subdir,
                    )
                except FileTooLargeError:
                    raise
                except Exception as e:
                    last_err = e
                    cat = classify_error(e)
                    if cat in ("private", "not_found", "geo_blocked", "live", "music_unsupported", "bad_url"):
                        self._raise_categorized(e)
                    self._fire_source_failed(f"vk.ytdlp.doc.{name}", e)

            if last_err:
                self._raise_categorized(last_err)
            raise VkDownloadError("download_failed")
        except BaseException:
            self.cleanup_dir(subdir)
            raise

    def _attach_progress_hook(self, opts: dict, progress_callback: ProgressCallback) -> None:
        last = {"t": 0.0}

        def _hook(d):
            if d.get("status") != "downloading":
                return
            now = time.time()
            if now - last["t"] < 3:
                return
            last["t"] = now
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            if total > 0:
                percent = int(downloaded / total * 100)
                progress_callback(
                    downloaded / 1024 / 1024,
                    total / 1024 / 1024,
                    percent,
                )

        opts["progress_hooks"] = [_hook]

    def _find_downloaded_file_in(self, info: dict, subdir: str) -> str | None:
        """Найти файл, который yt-dlp только что скачал, СТРОГО внутри subdir.

        Это защищает от race condition: мы не можем случайно вернуть файл
        другого юзера (каждый вызов download использует свой subdir).
        """
        # yt-dlp кладёт путь в 'requested_downloads'
        req = info.get("requested_downloads") or []
        for r in req:
            p = r.get("filepath") or r.get("_filename")
            if p and os.path.exists(p) and os.path.commonpath([p, subdir]) == subdir:
                return p
        # fallback — файл внутри subdir (там должен быть только один)
        candidates = []
        if os.path.isdir(subdir):
            for fname in os.listdir(subdir):
                fp = os.path.join(subdir, fname)
                if os.path.isfile(fp) and not fname.endswith(".part"):
                    candidates.append((os.path.getmtime(fp), fp))
        if not candidates:
            return None
        candidates.sort(reverse=True)
        return candidates[0][1]

    # ================ INTERNALS: gallery-dl ================

    async def _gallerydl_info(self, url: str, media_type: str) -> VkMediaInfo:
        """Получить метаданные через gallery-dl (info-режим, без скачивания).

        gallery-dl возвращает JSON-lines, из которых можно посчитать кол-во файлов.
        """
        # gallery-dl --simulate -j возвращает NDJSON метаданные
        attempts = self._gallerydl_attempts()
        last_err: Exception | None = None
        for name, extra_args in attempts:
            try:
                items = await self._run_gallerydl_simulate(url, extra_args)
                title = ""
                if items:
                    title = (
                        items[0].get("title")
                        or items[0].get("album_title")
                        or items[0].get("description")
                        or "VK"
                    )[:200]
                return VkMediaInfo(
                    media_type=media_type,
                    title=title or "VK",
                    item_count=len(items),
                    attachments=[
                        {"type": it.get("extension", "photo"), "url": it.get("url", "")}
                        for it in items
                    ],
                )
            except Exception as e:
                last_err = e
                cat = classify_error(e)
                if cat in ("private", "not_found", "geo_blocked", "live", "music_unsupported", "bad_url"):
                    self._raise_categorized(e)
                logger.warning("gallery-dl info [%s] упал: %s", name, e)
                self._fire_source_failed(f"vk.gdl.{name}", e)

        if last_err:
            self._raise_categorized(last_err)
        raise VkDownloadError("get_info_failed")

    def _gallerydl_attempts(self) -> list[tuple[str, list[str]]]:
        """Порядок попыток для gallery-dl (аналогично yt-dlp-цепочке)."""
        attempts: list[tuple[str, list[str]]] = [("primary", [])]
        if self._proxy:
            attempts.append(("proxy", ["--proxy", self._proxy]))
        attempts.append(("warp", ["--proxy", self.WARP_PROXY]))
        if self.has_cookies():
            attempts.append(("cookies", ["--cookies", self._COOKIES_PATH]))
        if self._proxy and self.has_cookies():
            attempts.append(
                ("proxy+cookies", ["--proxy", self._proxy, "--cookies", self._COOKIES_PATH])
            )
        if self.has_cookies():
            attempts.append(
                ("warp+cookies", ["--proxy", self.WARP_PROXY, "--cookies", self._COOKIES_PATH])
            )
        return attempts

    async def _run_gallerydl_simulate(self, url: str, extra_args: list[str]) -> list[dict]:
        """Запустить gallery-dl в режиме simulate+json, вернуть список метаданных."""
        cmd = [
            "gallery-dl",
            "-j",                     # JSON output
            "--simulate",
            *extra_args,
            url,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            raise VkDownloadError("gallery-dl simulate timeout")
        if proc.returncode != 0:
            err = stderr.decode(errors="replace")[:500]
            raise VkDownloadError(f"gallery-dl failed: {err}")

        # gallery-dl -j отдаёт один большой JSON-массив из [type, url, metadata]
        text = stdout.decode(errors="replace").strip()
        if not text:
            return []
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # иногда gallery-dl пишет NDJSON — пробуем построчно
            items: list[dict] = []
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, list) and len(obj) >= 3 and isinstance(obj[2], dict):
                        items.append(obj[2])
                    elif isinstance(obj, dict):
                        items.append(obj)
                except json.JSONDecodeError:
                    continue
            return items

        # стандартный gallery-dl -j: [[type, url, metadata], ...]
        items: list[dict] = []
        if isinstance(data, list):
            for entry in data:
                if isinstance(entry, list) and len(entry) >= 3 and isinstance(entry[2], dict):
                    meta = dict(entry[2])
                    if isinstance(entry[1], str):
                        meta.setdefault("url", entry[1])
                    items.append(meta)
        return items

    async def _gallerydl_download(self, url: str) -> list[DownloadedItem]:
        """Скачать все медиа через gallery-dl. Возвращает список файлов.

        Создаёт per-call out_dir — хендлер должен удалить его через shutil.rmtree
        (он передан в каждом DownloadedItem.work_dir).
        """
        out_dir = tempfile.mkdtemp(prefix="vk_gdl_", dir=self.download_dir)
        last_err: Exception | None = None
        for name, extra_args in self._gallerydl_attempts():
            try:
                files = await self._run_gallerydl_download(url, out_dir, extra_args)
                if not files:
                    raise VkDownloadError("gallery-dl produced no files")
                items: list[DownloadedItem] = []
                for fp in files:
                    ext = os.path.splitext(fp)[1].lower()
                    if ext in (".mp4", ".mov", ".m4v", ".webm"):
                        mt = "video"
                    elif ext in (".gif",):
                        mt = "animation"
                    elif ext in (".mp3", ".m4a", ".ogg", ".opus", ".wav"):
                        mt = "audio"
                    elif ext in (".jpg", ".jpeg", ".png", ".webp"):
                        mt = "photo"
                    else:
                        mt = "document"

                    size = os.path.getsize(fp) if os.path.exists(fp) else 0
                    if size > MAX_FILE_SIZE:
                        # слишком большое одиночное вложение — пропускаем, файл удаляем
                        self.cleanup_file(fp)
                        continue
                    items.append(DownloadedItem(file_path=fp, media_type=mt, work_dir=out_dir))
                if not items:
                    raise FileTooLargeError("all_attachments_too_large")
                return items
            except FileTooLargeError:
                self.cleanup_dir(out_dir)
                raise
            except Exception as e:
                last_err = e
                cat = classify_error(e)
                if cat in ("private", "not_found", "geo_blocked", "live", "music_unsupported", "bad_url"):
                    # чистим out_dir и пробрасываем
                    self.cleanup_dir(out_dir)
                    self._raise_categorized(e)
                logger.warning("gallery-dl download [%s] упал: %s", name, e)
                self._fire_source_failed(f"vk.gdl.{name}", e)

        self.cleanup_dir(out_dir)
        if last_err:
            self._raise_categorized(last_err)
        raise VkDownloadError("download_failed")

    async def _run_gallerydl_download(
        self, url: str, out_dir: str, extra_args: list[str],
    ) -> list[str]:
        """Запустить gallery-dl в download-режиме. Возвращает список скачанных файлов."""
        cmd = [
            "gallery-dl",
            "-D", out_dir,                 # dest directory
            "--no-mtime",
            "--range", f"1-{MAX_ALBUM_ITEMS}",
            *extra_args,
            url,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            raise VkDownloadError("gallery-dl download timeout")
        err_text = stderr.decode(errors="replace")[:1000]
        out_text = stdout.decode(errors="replace")[:500]
        if proc.returncode != 0:
            raise VkDownloadError(f"gallery-dl download failed: {err_text}")

        # собираем все скачанные файлы из out_dir
        result = []
        for root, _, files in os.walk(out_dir):
            for f in files:
                # gallery-dl оставляет .part при ошибках — пропускаем
                if f.endswith(".part") or f.endswith(".json"):
                    continue
                result.append(os.path.join(root, f))
        result.sort()
        if not result:
            # returncode=0 но нет файлов — обычно auth required / приват / удалено.
            # Логируем stderr чтобы диагностировать причину, классифицируем как приват.
            logger.warning(
                "gallery-dl returncode=0 но 0 файлов. stderr=%s stdout=%s url=%s",
                err_text.strip(), out_text.strip(), url,
            )
            msg = (err_text + " " + out_text).lower()
            if "login" in msg or "auth" in msg or "sign" in msg or "cookies" in msg:
                raise PrivateContentError(f"gallery-dl auth required: {err_text[:200]}")
            if "not found" in msg or "404" in msg or "removed" in msg:
                raise ContentUnavailableError(f"gallery-dl not found: {err_text[:200]}")
            # дефолт: контент недоступен (обычно приват или удалено)
            raise ContentUnavailableError(f"gallery-dl produced no files: {err_text[:200]}")
        return result

    # ================ ERROR ROUTING ================

    def _raise_categorized(self, exc: BaseException) -> None:
        """Преобразует низкоуровневую ошибку в доменное исключение."""
        if isinstance(exc, (FileTooLargeError, PrivateContentError, ContentUnavailableError,
                            MusicNotSupportedError, LiveStreamError)):
            raise exc
        cat = classify_error(exc)
        if cat == "live":
            raise LiveStreamError(str(exc)) from exc
        if cat == "private":
            raise PrivateContentError(str(exc)) from exc
        if cat in ("not_found", "geo_blocked", "bad_url"):
            raise ContentUnavailableError(str(exc)) from exc
        if cat == "too_large":
            raise FileTooLargeError(str(exc)) from exc
        if cat == "music_unsupported":
            raise MusicNotSupportedError(str(exc)) from exc
        raise VkDownloadError(str(exc)) from exc


# Глобальный экземпляр — импортируется из хэндлеров
downloader = VkDownloader()
