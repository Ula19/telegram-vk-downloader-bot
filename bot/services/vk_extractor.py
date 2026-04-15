"""Экстрактор типа VK-ссылки.

Поддерживаемые форматы URL:
  /video-X_Y, /clip-X_Y, /photo-X_Y, /album-X_Y, /wall-X_Y, /story-X_Y, /doc-X_Y
  /@slug, /@channel/video-X_Y
  /playlist/-X_Y/video-X_Y (нормализуем в /video-X_Y)
  /video_ext.php?oid=X&id=Y
  legacy: ?z=video-X_Y, ?z=clip-X_Y, ?w=wall-X_Y, ?w=photo-X_Y, ?w=album-X_Y
  хосты: vk.com, vk.ru, vkvideo.ru, vk.video (любой поддомен)
  короткие: vk.cc/X, vk.link/X — раскрываются через HTTP-редирект.

Определяем что именно прислал юзер:
  - Видео: vk.com/video-{owner}_{id}, vkvideo.ru/video-...
  - Клипы: vk.com/clip-{owner}_{id}
  - Фото: vk.com/photo{owner}_{id}
  - Альбом: vk.com/album{owner}_{id}
  - Пост: vk.com/wall{owner}_{id}, vk.com/@name-slug (внутренний пост)
  - Сторис: vk.com/story{owner}_{id}
  - Документ: vk.com/doc{owner}_{id}
  - Embedded плеер: vk.com/video_ext.php?...
  - Канал VK Видео: vkvideo.ru/@channel/...
"""
import re
from enum import Enum
from urllib.parse import parse_qs, urlparse


class VkMediaType(str, Enum):
    VIDEO = "video"
    CLIP = "clip"
    PHOTO = "photo"
    ALBUM = "album"
    WALL_POST = "wall_post"
    STORY = "story"
    DOC = "doc"
    CHANNEL = "channel"
    VIDEO_EXT = "video_ext"
    UNKNOWN = "unknown"


# Регулярные паттерны.
# owner_id может быть отрицательным (группа, "-1234"), mediaid — число.
_RE_VIDEO_PATH = re.compile(r"/video(-?\d+)_(\d+)", re.IGNORECASE)
_RE_PLAYLIST_VIDEO = re.compile(
    r"/playlist/-?\d+_\d+/(video-?\d+_\d+)", re.IGNORECASE,
)
_RE_CLIP_PATH = re.compile(r"/clip(-?\d+)_(\d+)", re.IGNORECASE)
_RE_PHOTO_PATH = re.compile(r"/photo(-?\d+)_(\d+)", re.IGNORECASE)
_RE_ALBUM_PATH = re.compile(r"/album(-?\d+)_(-?\d+)", re.IGNORECASE)
_RE_WALL_PATH = re.compile(r"/wall(-?\d+)_(\d+)", re.IGNORECASE)
_RE_STORY_PATH = re.compile(r"/story(-?\d+)_(\d+)", re.IGNORECASE)
_RE_DOC_PATH = re.compile(r"/doc(-?\d+)_(\d+)", re.IGNORECASE)
_RE_AT_SLUG = re.compile(r"/@([\w.\-]+)(?:/([\w.\-/]+))?", re.IGNORECASE)

# legacy-формы: vk.com/feed?w=wall-X_Y_Z, vk.com/something?z=video-X_Y,
# vk.com/away.php?to=... , vk.com/wall.php?act=...
_RE_Z_VIDEO = re.compile(r"video(-?\d+)_(\d+)", re.IGNORECASE)
_RE_Z_CLIP = re.compile(r"clip(-?\d+)_(\d+)", re.IGNORECASE)
_RE_W_WALL = re.compile(r"wall(-?\d+)_(\d+)", re.IGNORECASE)
_RE_W_PHOTO = re.compile(r"photo(-?\d+)_(\d+)", re.IGNORECASE)
_RE_W_ALBUM = re.compile(r"album(-?\d+)_(-?\d+)", re.IGNORECASE)

# Короткие ссылки vk.cc / vk.link — требуют HEAD-запроса для раскрытия
SHORT_LINK_HOSTS = {"vk.cc", "vk.link"}


def detect_vk_media_type(url: str) -> VkMediaType:
    """Определить тип VK-медиа по URL."""
    if not url:
        return VkMediaType.UNKNOWN

    try:
        parsed = urlparse(url.strip())
    except Exception:
        return VkMediaType.UNKNOWN

    host = (parsed.netloc or "").lower()
    path = parsed.path or ""
    query = parsed.query or ""

    # video_ext.php — встраиваемый плеер
    if "video_ext.php" in path:
        return VkMediaType.VIDEO_EXT

    # vkvideo.ru/@channel/... — канал VK Видео
    # если дальше есть /video... — это видео этого канала
    if "vkvideo.ru" in host or "vk.video" in host:
        if _RE_VIDEO_PATH.search(path):
            return VkMediaType.VIDEO
        if _RE_CLIP_PATH.search(path):
            return VkMediaType.CLIP
        if path.startswith("/@") or _RE_AT_SLUG.match(path):
            return VkMediaType.CHANNEL

    if _RE_CLIP_PATH.search(path):
        return VkMediaType.CLIP
    if _RE_VIDEO_PATH.search(path):
        return VkMediaType.VIDEO
    if _RE_WALL_PATH.search(path):
        return VkMediaType.WALL_POST
    if _RE_ALBUM_PATH.search(path):
        return VkMediaType.ALBUM
    if _RE_PHOTO_PATH.search(path):
        return VkMediaType.PHOTO
    if _RE_STORY_PATH.search(path):
        return VkMediaType.STORY
    if _RE_DOC_PATH.search(path):
        return VkMediaType.DOC

    # vk.com/@slug — обычно пост-статья или короткий профиль
    if _RE_AT_SLUG.match(path):
        return VkMediaType.WALL_POST

    # Legacy query-notation: ?z=video-X_Y / ?z=photo-X_Y / ?w=wall-X_Y / ?w=page-X_Y
    q = parse_qs(query)
    z_val = (q.get("z", [""])[0] or "").split("/")[0]
    w_val = (q.get("w", [""])[0] or "").split("_", 2)[0] + "_" + "_".join((q.get("w", [""])[0] or "").split("_")[1:]) if "w" in q else ""
    combined = f"{z_val} {q.get('w', [''])[0]}"
    if _RE_Z_VIDEO.search(combined):
        return VkMediaType.VIDEO
    if _RE_Z_CLIP.search(combined):
        return VkMediaType.CLIP
    if _RE_W_WALL.search(combined):
        return VkMediaType.WALL_POST
    if _RE_W_PHOTO.search(combined):
        return VkMediaType.PHOTO
    if _RE_W_ALBUM.search(combined):
        return VkMediaType.ALBUM

    # /video?list=... — тоже видео (редкий случай без video-X_Y в path)
    if "/video" in path and "list" in q:
        return VkMediaType.VIDEO

    return VkMediaType.UNKNOWN


def parse_vk_ids(url: str) -> tuple[int | None, int | None]:
    """Извлечь (owner_id, media_id) из VK-URL. (None, None) если не распарсилось."""
    if not url:
        return (None, None)
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return (None, None)
    path = parsed.path or ""

    for pattern in (
        _RE_CLIP_PATH, _RE_VIDEO_PATH, _RE_WALL_PATH,
        _RE_PHOTO_PATH, _RE_ALBUM_PATH, _RE_STORY_PATH, _RE_DOC_PATH,
    ):
        m = pattern.search(path)
        if m:
            try:
                return (int(m.group(1)), int(m.group(2)))
            except ValueError:
                return (None, None)

    # video_ext.php?oid=...&id=...
    if "video_ext.php" in path:
        q = parse_qs(parsed.query)
        oid = q.get("oid", [None])[0]
        vid = q.get("id", [None])[0]
        try:
            if oid and vid:
                return (int(oid), int(vid))
        except ValueError:
            pass

    return (None, None)


async def resolve_short_link(url: str, timeout: float = 5.0) -> str:
    """Раскрыть короткую VK-ссылку (vk.cc/vk.link) в полный URL через HEAD-редирект.

    Если URL не короткий — возвращаем как есть. При сбое сети тоже возвращаем
    исходный URL (лучше попытаться обработать, чем бросать ошибку).
    """
    if not url:
        return url
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return url.strip()
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host not in SHORT_LINK_HOSTS:
        return url.strip()

    import asyncio

    import aiohttp

    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(
                url, allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                final = str(resp.url)
                return final or url
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return url.strip()


def normalize_vk_url(url: str) -> str:
    """Привести URL к каноничной форме (убрать трекинговые параметры, m.-префиксы).
    Используется как ключ кэша.
    """
    if not url:
        return url
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return url.strip()

    host = (parsed.netloc or "").lower()
    # m.vk.com → vk.com
    if host.startswith("m."):
        host = host[2:]
    if host.startswith("www."):
        host = host[4:]
    # vk.ru — зеркало vk.com (с 2023 г.); нормализуем к vk.com для единого ключа кэша
    if host == "vk.ru":
        host = "vk.com"

    # /playlist/-X_Y/video-X_Y → /video-X_Y (yt-dlp корректнее обрабатывает
    # одиночное видео, а не плейлист — это ускоряет get_info и исключает
    # цикл фолбэков при скачивании).
    path = parsed.path or ""
    m = _RE_PLAYLIST_VIDEO.search(path)
    if m:
        path = "/" + m.group(1)

    # Legacy query-notation: vk.com/feed?z=video-X_Y_xxx → /video-X_Y
    # vk.com/feed?w=wall-X_Y → /wall-X_Y. Конвертируем в канонический путь,
    # т.к. yt-dlp/gallery-dl ожидают именно такой формат.
    q_raw = parsed.query or ""
    q_parsed = parse_qs(q_raw)
    z_val = (q_parsed.get("z", [""])[0] or "")
    w_val = (q_parsed.get("w", [""])[0] or "")
    legacy = z_val + " " + w_val
    rewritten_path = None
    for pat in (_RE_Z_VIDEO, _RE_Z_CLIP, _RE_W_WALL, _RE_W_PHOTO, _RE_W_ALBUM):
        m2 = pat.search(legacy)
        if m2:
            rewritten_path = "/" + m2.group(0)
            break
    if rewritten_path:
        path = rewritten_path
        q_raw = ""  # после переписывания query-хвост не нужен

    # убираем служебные параметры (UTM, плейлист-хинты)
    keep_params = []
    if q_raw:
        for pair in q_raw.split("&"):
            if not pair:
                continue
            key = pair.split("=", 1)[0].lower()
            if key.startswith("utm_") or key in ("from", "t", "ref", "list", "linked", "z"):
                continue
            keep_params.append(pair)
    query = "&".join(keep_params)

    rebuilt = f"https://{host}{path}"
    if query:
        rebuilt += f"?{query}"
    return rebuilt
