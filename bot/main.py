"""Точка входа — запуск VK-бота"""
import asyncio
import logging
import os
import sys
import time

# uvloop ускоряет asyncio в 2-4 раза (не работает на Windows!)
try:
    import uvloop
    uvloop.install()
except ImportError:
    pass  # на Windows — работаем без uvloop

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent

from bot.config import settings

# настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# флаг-файл для crash recovery
CRASH_FLAG = ".crash_flag"


async def main() -> None:
    """Инициализация и запуск бота"""
    # подключаемся к Local Bot API если указан URL
    session = None
    api_url = settings.bot_api_url
    if api_url != "https://api.telegram.org":
        # Local Bot API — файлы до 2 ГБ
        # Увеличиваем таймаут для загрузки больших файлов (по умолчанию 60 сек)
        session = AiohttpSession(
            api=TelegramAPIServer.from_base(api_url, is_local=True),
            timeout=600  # 10 минут на запрос
        )
        logger.info(f"Local Bot API: {api_url}")

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=session,
    )
    dp = Dispatcher(storage=MemoryStorage())

    # подключаем хэндлеры (порядок важен!)
    from bot.handlers import start, admin, download
    dp.include_router(start.router)
    dp.include_router(admin.router)
    dp.include_router(download.router)  # последний — ловит все текстовые сообщения с VK-ссылками

    # подключаем алерты админу о падении источников (proxy/WARP/cookies)
    download.setup_fallback_alerts(bot)

    # подключаем мидлвари
    from bot.middlewares.rate_limit import RateLimitMiddleware
    from bot.middlewares.subscription import SubscriptionMiddleware

    dp.message.middleware(RateLimitMiddleware())
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())

    @dp.errors()
    async def on_error(event: ErrorEvent) -> bool:
        """Глобальный error-handler: транзиентные сетевые сбои (Local Bot API keep-alive
        разорвал, ServerDisconnected, ConnectionReset) — логируем как WARNING и
        глотаем, aiogram на уровне polling сам восстановит соединение."""
        exc = event.exception
        if isinstance(exc, TelegramNetworkError):
            logger.warning("Сетевой сбой Telegram (транзиент): %s", exc)
            return True
        if isinstance(exc, TelegramRetryAfter):
            logger.warning("Telegram просит подождать %ds", exc.retry_after)
            return True
        logger.exception("Необработанная ошибка в хендлере: %s", exc)
        return True

    # события старта и остановки
    async def _background_cleanup() -> None:
        """Фоновая задача: чистит память + Local Bot API + зависшие temp-директории.

        Стратегия для /tmp/vk_bot_*:
          - Хендлеры чистят свою subdir через try/finally (первичная очистка).
          - Этот cleaner — safety net на случай crash / OOM / SIGKILL.
          - Удаляем subdir ТОЛЬКО если в ней никто не писал >30 минут
            (значит скачивание закончилось либо упало, файлы не нужны).
        """
        import glob
        import shutil
        from bot.middlewares.rate_limit import cleanup_stale_entries
        from bot.services.vk import downloader as _dl
        while True:
            await asyncio.sleep(300)  # 5 минут
            # чистим протухшие записи rate limit (memory leak)
            removed = cleanup_stale_entries()
            if removed:
                logger.info("Фоновая очистка: удалено %d записей rate limit", removed)

            now = time.time()

            # === safety-net для /tmp/vk_bot_*/ytv_*, /tmp/vk_bot_*/vk_gdl_* ===
            # (subdir активного скачивания, если хендлер упал до finally).
            # Смотрим mtime самого свежего файла внутри — если >30 мин назад, удаляем.
            vk_cleaned = 0
            parent = getattr(_dl, "download_dir", "")
            if parent and os.path.isdir(parent):
                for subdir in glob.glob(os.path.join(parent, "*")):
                    if not os.path.isdir(subdir):
                        continue
                    try:
                        latest_mtime = max(
                            (os.path.getmtime(os.path.join(root, f))
                             for root, _, files in os.walk(subdir)
                             for f in files),
                            default=os.path.getmtime(subdir),
                        )
                        if now - latest_mtime > 30 * 60:  # 30 минут бездействия
                            shutil.rmtree(subdir, ignore_errors=True)
                            vk_cleaned += 1
                    except OSError:
                        pass
            if vk_cleaned:
                logger.info("Safety net: удалено %d зависших VK subdir", vk_cleaned)

            # чистим файлы Local Bot API (старше 1 часа) — артефакты TDLib,
            # хендлеры их не трогают, безопасны для чистки по mtime.
            bot_api_cutoff = now - 60 * 60
            bot_api_cleaned = 0
            for f in glob.glob("/var/lib/telegram-bot-api/**/*", recursive=True):
                try:
                    if os.path.isfile(f) and os.path.getmtime(f) < bot_api_cutoff:
                        os.remove(f)
                        bot_api_cleaned += 1
                except OSError:
                    pass
            if bot_api_cleaned:
                logger.info("Фоновая очистка: удалено %d файлов Local Bot API", bot_api_cleaned)
            # чистим протухшие записи кэша VK-медиа
            try:
                from bot.database import async_session
                from bot.database.crud import cleanup_expired_vk_cache
                async with async_session() as session:
                    removed_cache = await cleanup_expired_vk_cache(session)
                if removed_cache:
                    logger.info("Фоновая очистка: удалено %d записей VK-кэша", removed_cache)
            except Exception as e:
                logger.warning("Ошибка чистки VK-кэша: %s", e)

    @dp.startup()
    async def on_startup() -> None:
        # создаём таблицы в БД
        from bot.database import engine
        from bot.database.models import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Таблицы БД созданы")

        # проверяем crash recovery
        if os.path.exists(CRASH_FLAG):
            logger.warning("Обнаружен crash-flag — предыдущий запуск завершился аварийно")
            os.remove(CRASH_FLAG)

        # ставим crash-flag (уберём при нормальном завершении)
        with open(CRASH_FLAG, "w") as f:
            f.write("running")

        # запускаем фоновую очистку
        asyncio.create_task(_background_cleanup())
        logger.info("Фоновая очистка запущена (интервал 5 мин)")

        bot_info = await bot.get_me()
        logger.info(f"Бот @{bot_info.username} запущен!")

        # ставим дефолтное меню команд (глобально, для новых юзеров)
        from bot.utils.commands import set_default_commands
        await set_default_commands(bot)
        logger.info("Дефолтное меню команд установлено")

    @dp.shutdown()
    async def on_shutdown() -> None:
        # убираем crash-flag при нормальном завершении
        if os.path.exists(CRASH_FLAG):
            os.remove(CRASH_FLAG)
        # чистим рабочую директорию загрузчика
        try:
            import shutil
            from bot.services.vk import downloader
            shutil.rmtree(downloader.download_dir, ignore_errors=True)
            logger.info("Очищена download_dir: %s", downloader.download_dir)
        except Exception as e:
            logger.warning("Не удалось очистить download_dir: %s", e)
        logger.info("Бот остановлен")

    # запускаем polling
    try:
        logger.info("Запуск polling...")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
