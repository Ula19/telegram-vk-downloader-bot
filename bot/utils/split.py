"""Автосплит крупных видео через ffmpeg -c copy.

Telegram Local Bot API принимает файлы до 2 ГБ. Если скачанное VK-видео
превысило лимит — режем на части без перекодирования (по длительности,
рассчитанной из bitrate), чтобы каждая ~1.9 ГБ.
"""
import asyncio
import logging
import math
import os
from pathlib import Path

logger = logging.getLogger(__name__)


async def get_video_duration(input_path: str) -> float:
    """Вернуть длительность видео в секундах через ffprobe. 0.0 при ошибке."""
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        input_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    try:
        return float(stdout.decode().strip())
    except (ValueError, AttributeError):
        logger.warning("ffprobe duration failed: %s", stderr.decode() if stderr else "")
        return 0.0


async def split_video(
    input_path: str,
    output_dir: str,
    max_size_bytes: int = int(1.9 * 1024 * 1024 * 1024),
) -> list[str]:
    """Разрезать видео на куски ~max_size_bytes через ffmpeg -c copy (быстро, без перекодирования).

    Возвращает список путей к частям в порядке воспроизведения.
    Если видео меньше лимита — возвращает [input_path].
    """
    size = os.path.getsize(input_path)
    if size <= max_size_bytes:
        return [input_path]

    duration = await get_video_duration(input_path)
    if duration <= 0:
        logger.warning("Не удалось определить длительность — сплит невозможен")
        return [input_path]

    # сколько частей нужно
    parts = math.ceil(size / max_size_bytes)
    segment_seconds = math.ceil(duration / parts) + 1

    os.makedirs(output_dir, exist_ok=True)
    base_name = Path(input_path).stem
    output_pattern = os.path.join(output_dir, f"{base_name}_part_%03d.mp4")

    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", input_path,
        "-c", "copy",
        "-map", "0",
        "-f", "segment",
        "-segment_time", str(segment_seconds),
        "-reset_timestamps", "1",
        output_pattern,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        logger.error("ffmpeg split failed: %s", stderr.decode()[-500:] if stderr else "")
        return [input_path]

    # собираем куски в порядке
    result = sorted(
        str(p) for p in Path(output_dir).glob(f"{base_name}_part_*.mp4")
    )
    if not result:
        return [input_path]
    return result
