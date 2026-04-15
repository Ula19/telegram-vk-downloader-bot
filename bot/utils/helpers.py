"""Хелперы — валидация VK-ссылок, форматирование."""
import re


# Охватывает все поддерживаемые форматы VK-ссылок:
#   vk.com / m.vk.com / vkvideo.ru / vk.video
#   /video-... /clip-... /photo... /album... /wall... /story... /doc... /@slug
#   /video_ext.php?... /video?list=...
_VK_HOSTS = re.compile(
    r"https?://(?:[\w-]+\.)*(vk\.com|vk\.ru|vkvideo\.ru|vk\.video|vk\.cc|vk\.link)/",
    re.IGNORECASE,
)
_ANY_URL = re.compile(r"https?://\S+", re.IGNORECASE)


def is_vk_url(text: str) -> bool:
    """Проверяет, похоже ли это на ссылку ВКонтакте/VK Видео (любой поддомен)."""
    if not text:
        return False
    return bool(_VK_HOSTS.search(text.strip()))


def looks_like_url(text: str) -> bool:
    """Проверяет, есть ли в тексте http(s)-ссылка (любого домена)."""
    if not text:
        return False
    return bool(_ANY_URL.search(text.strip()))


def format_duration(seconds: int | float | None) -> str:
    """Форматирует длительность в HH:MM:SS или MM:SS."""
    if not seconds:
        return "—"
    try:
        s = int(seconds)
    except (TypeError, ValueError):
        return "—"
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h:d}:{m:02d}:{sec:02d}"
    return f"{m:d}:{sec:02d}"


def human_size_mb(size_bytes: int | float) -> str:
    """Красивый размер в МБ."""
    if not size_bytes:
        return "—"
    mb = size_bytes / 1024 / 1024
    if mb < 1:
        return "<1 МБ"
    return f"{mb:.0f} МБ"
