# bot_4_vk — VK Downloader Bot

Telegram-бот для скачивания видео и медиа из ВКонтакте / VK Видео.

## Что умеет

Поддерживаемые ссылки (включая `vk.com`, `vk.ru`, `m.vk.com`, `vkvideo.ru`, любые поддомены, короткие `vk.cc`/`vk.link`):

- **Видео и VK Видео**: `vk.com/video-..._...`, `vkvideo.ru/video-...` — выбор качества (240p–1080p+)
- **Клипы**: `vk.com/clip-..._...` — короткие вертикальные
- **Фото**: `vk.com/photo-..._...` — одиночные
- **Альбомы**: `vk.com/album-..._...` — пачки по 10 через `send_media_group`
- **Посты со стены**: `vk.com/wall-..._...`, `vk.com/@slug` — все вложения (фото+видео+документы), текст поста приходит отдельным сообщением
- **Сторис** (если публичные)
- **Документы**: `vk.com/doc..._...` — GIF/mp3/произвольные файлы
- **Embedded-плеер**: `vk.com/video_ext.php?oid=X&id=Y`
- **Legacy-формы**: `?z=video-X_Y`, `?w=wall-X_Y`, `/playlist/-X_Y/video-X_Y?list=...`
- **Короткие ссылки**: `vk.cc/xxx`, `vk.link/xxx` — раскрываются через HTTP-редирект

Не поддерживается:

- **Музыка VK (Audio API)** — закрыто на стороне VK, юзер получает осмысленный отказ
- **Live-эфиры в реалтайме** — отдельная ошибка «Прямой эфир не поддерживается», можно скачать запись после окончания
- **Приватные/закрытые** — юзер-френдли ошибка «Закрытый профиль»

## Стек

- Python 3.12 + aiogram 3.26
- PostgreSQL 16 (SQLAlchemy async + asyncpg)
- Docker + Local Bot API (файлы до 2 ГБ)
- ffmpeg (автосплит видео >1.9 ГБ на части)
- **yt-dlp** — video/clip/video_ext/doc/wall-плейлисты
- **gallery-dl** — photo/album/post-карусели
- **Cloudflare WARP** (контейнер) — для обхода гео-блока при серверном IP
- i18n: русский / узбекский / английский

## Fallback-цепочка

Для каждого скачивания пробуем по очереди (стоп на первом успехе):

1. `primary` — прямое подключение (VK в РФ доступен напрямую)
2. `proxy` — SOCKS5/HTTP из `PROXY_URL` (резидентный прокси)
3. `warp` — Cloudflare WARP-контейнер `socks5://warp:9091` (клиентский IP, обход серверного блока)
4. `cookies` — `cookies/cookies.txt` (для 18+/приватного/сторис)
5. `proxy + cookies`
6. `warp + cookies`

Контентные ошибки (`private`, `not_found`, `geo_blocked`, `live`, `music_unsupported`) короткозамыкаются — fallback'и не ретраятся.

На каждом падении источника бот шлёт алерт админам через Telegram (троттлинг — 1 сообщение на пару `(источник, категория)` раз в 10 минут). При падении WARP с сетевой ошибкой — контейнер авто-перезапускается для смены IP (кулдаун 5 мин).

## Порты на сервере

Унифицированная раскладка (чтобы боты не конфликтовали):

| Бот | BOT_API_PORT |
|---|---|
| YouTube | 8081 |
| Instagram | 8082 |
| TikTok | 8091 |
| Twitter | 8092 |
| Facebook | 8093 |
| Twitch | 8094 |
| **VK** | **8095** |

Переопределяется через `BOT_API_PORT` в `.env`.

## Быстрый старт

```bash
cd /path/to/bot_4_vk

# 1. Подготовь .env
cp .env.example .env
# Заполни: BOT_TOKEN, API_ID, API_HASH, DB_PASSWORD, ADMIN_IDS, BOT_USERNAME

# 2. Создай пустую папку для cookies (даже если не используешь)
mkdir -p cookies

# 3. Подними
docker compose up -d --build

# 4. Проверь что всё здорово
docker compose ps
docker compose logs -f bot
docker compose logs warp | grep -i "warp=on"   # WARP healthy
```

Проверка пайплайна после деплоя — отправь боту несколько типов ссылок:

- `https://vk.com/video-22822305_456242787` — видео с выбором качества
- `https://vk.com/clip-227391694_456239101?c=1` — клип
- `https://vk.com/wall-141682278_983282` — пост с текстом и фото
- `https://vkvideo.ru/playlist/-231046280_2/video-231046280_456239593` — видео из плейлиста
- `https://vk.ru/story-...` — история
- `https://random-site.com/xxx` — должен ответить «Это не похоже на ссылку VK»

## Cookies (опционально)

Нужны для:
- 18+ контента
- Видео, доступных только друзьям
- Сторис непубличных аккаунтов

Экспорт cookies:
- Chrome: расширение «Get cookies.txt LOCALLY».
- Получившийся файл положи в `./cookies/cookies.txt` — docker-compose автоматически его подхватит (volume `./cookies:/app/cookies`).
- Обновление без рестарта — просто перезапиши файл в volume.

## Прокси (опционально)

VPS в Германии/EU часто имеет VK-заблокированный серверный IP. В этом случае:

1. **Резидентный SOCKS5**: пропиши в `.env` `PROXY_URL=socks5://user:pass@host:port`. Идёт как `proxy` в fallback-цепочке (шаг 2).
2. **WARP** — подключён по умолчанию как fallback (шаг 3). Контейнер `warp` поднимается автоматически из `docker-compose.yml`, healthcheck проверяет что подключение установлено.

Идеально задействовать оба: `proxy` — быстрый резидентный, `warp` — бесплатный safety net.

## Структура проекта

```
bot/
  main.py              # entrypoint + фоновая очистка, error-handler, WARP-hookup
  config.py            # BOT_TOKEN, DB_*, PROXY_URL, CACHE_TTL_DAYS
  i18n.py              # переводы ru/uz/en (~80 ключей)
  emojis.py            # премиум-emoji + fallback Unicode
  handlers/
    start.py           # /start, меню, профиль, язык, подписка
    admin.py           # админка: статистика, каналы, рассылка
    download.py        # VK-флоу + notify_admins setup
  services/
    vk.py              # VkDownloader: yt-dlp + gallery-dl, fallback, get_post_text
    vk_extractor.py    # detect_vk_media_type, normalize_vk_url, resolve_short_link
  utils/
    split.py           # split_video через ffmpeg -c copy (~1.9 ГБ куски)
    helpers.py         # is_vk_url, format_duration
    docker.py          # restart_warp (ротация WARP IP через Docker API)
    commands.py        # set_default_commands / set_user_commands
  middlewares/
    subscription.py    # проверка обязательной подписки
    rate_limit.py      # лимит скачиваний (5/мин на юзера)
  database/
    models.py          # User, Channel, VkMediaCache
    crud.py            # CRUD + cleanup_expired_vk_cache
```

## Диск и cleanup

Local Bot API **не чистит** файлы — делаем это сами:

- **Хендлер**: `try/finally` → `shutil.rmtree(subdir)` сразу после отправки (первичная очистка).
- **Safety net**: раз в 5 минут фоновая задача удаляет subdir в `/tmp/vk_bot_*`, в которые никто не писал >30 минут (покрывает crash/OOM/SIGKILL).
- **Local Bot API**: файлы `/var/lib/telegram-bot-api/**/*` старше 1 часа удаляются (TDLib докачивает клиентам до ~30 мин).
- **VK-кэш БД**: раз в 5 минут чистится по `CACHE_TTL_DAYS`.
- **Автосплит**: куски удаляются поимённо после отправки последнего.

## Кэш file_id

После первой отправки файла в Telegram кэшируем `file_id` в PostgreSQL:
- **Видео**: ключ `(url, quality, 0)`
- **Фото/документ**: `(url, "photo"|"doc", 0)`
- **Пост/альбом**: по элементам `(url, "post", item_index)` + `item_count` для проверки целостности (если в БД не все item'ы → кэш не используется).

TTL управляется `CACHE_TTL_DAYS` (дефолт 1). Если Telegram вернул ошибку на кэшированный file_id — перезакачиваем и обновляем запись.

## Админ-команды

- `/admin` — админ-панель (статистика, список каналов, рассылка)
- `/update_cookies` — залить `cookies.txt` через Telegram без рестарта контейнера (TODO: не реализован — клади файл руками в `./cookies/`)

Админы задаются в `.env` как `ADMIN_IDS=111,222,333`.

## Мониторинг

После деплоя смотри:

```bash
docker compose logs -f bot       # поток событий и ошибок
docker compose logs warp         # статус WARP
docker compose ps                # health всех сервисов
```

Алерты о падении источников приходят прямо в Telegram админам (форматированные: `⚠️ Источник упал! Источник: proxy / Категория: network / Ошибка: ...`).

## Бэкап

Рекомендуется настроить cron-задачу на сервере:

```bash
# /etc/cron.daily/bot_4_vk_backup
docker compose exec postgres pg_dump -U bot_user bot_4_vk | gzip > /backup/bot_4_vk_$(date +%F).sql.gz
```

Что хранится: юзеры, каналы подписки, кэш `file_id`. Потеря кэша не критична — перекачается при следующем обращении.
