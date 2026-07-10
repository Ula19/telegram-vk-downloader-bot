"""Мультиязычность — русский, узбекский, английский
Использование: from bot.i18n import t
  t("start.welcome", lang="en", name="John")
"""

from bot.emojis import E

TRANSLATIONS = {
    # === /start ===
    "start.welcome": {
        "ru": (
            f"{E['bot']} <b>Привет, {{name}}!</b>\n\n"
            f"{E['video']} Я помогу тебе скачать видео и медиа из ВКонтакте.\n\n"
            f"{E['pin']} <b>Как пользоваться:</b>\n"
            "Просто отправь мне ссылку на пост, видео или клип ВКонтакте — "
            f"и я скачаю его для тебя! {E['plane']}\n\n"
            "Выбери действие ниже:"
        ),
        "uz": (
            f"{E['bot']} <b>Salom, {{name}}!</b>\n\n"
            f"{E['video']} VKontakte'dan video va media yuklab olishda yordam beraman.\n\n"
            f"{E['pin']} <b>Qanday foydalanish:</b>\n"
            "Menga VKontakte post, video yoki klip havolasini yuboring — "
            f"men senga yuklab beraman! {E['plane']}\n\n"
            "Quyidagi tugmani tanlang:"
        ),
        "en": (
            f"{E['bot']} <b>Hello, {{name}}!</b>\n\n"
            f"{E['video']} I'll help you download videos and media from VKontakte.\n\n"
            f"{E['pin']} <b>How to use:</b>\n"
            "Just send me a VKontakte post, video or clip link — "
            f"and I'll download it for you! {E['plane']}\n\n"
            "Choose an action below:"
        ),
    },

    # === Кнопки главного меню ===
    "btn.download": {
        "ru": "Скачать из VK",
        "uz": "VK dan yuklab olish",
        "en": "Download from VK",
    },
    "btn.profile": {
        "ru": "Мой профиль",
        "uz": "Mening profilim",
        "en": "My profile",
    },
    "btn.help": {
        "ru": "Помощь",
        "uz": "Yordam",
        "en": "Help",
    },
    "btn.back": {
        "ru": "Назад",
        "uz": "Orqaga",
        "en": "Back",
    },
    "btn.language": {
        "ru": "Сменить язык",
        "uz": "Tilni o'zgartirish",
        "en": "Change language",
    },

    # === Кнопки формата и качества ===
    "btn.format_video": {
        "ru": "Видео (MP4)",
        "uz": "Video (MP4)",
        "en": "Video (MP4)",
    },
    "btn.format_audio": {
        "ru": "Аудио",
        "uz": "Audio",
        "en": "Audio",
    },
    "btn.download_audio_instead": {
        "ru": "Скачать аудио вместо видео",
        "uz": "Video o'rniga audio yuklab olish",
        "en": "Download audio instead",
    },

    # === Скачивание ===
    "download.prompt": {
        "ru": (
            f"{E['download']} <b>Скачивание из ВКонтакте</b>\n\n"
            "Отправь мне ссылку на:\n"
            "• Видео\n"
            "• VK Видео\n"
            "• Клипы\n\n"
            f"{E['link']} Пример: <code>https://vk.com/video-1234567_789</code>"
        ),
        "uz": (
            f"{E['download']} <b>VKontakte'dan yuklab olish</b>\n\n"
            "Menga havola yuboring:\n"
            "• Video\n"
            "• VK Video\n"
            "• Kliplar\n\n"
            f"{E['link']} Misol: <code>https://vk.com/video-1234567_789</code>"
        ),
        "en": (
            f"{E['download']} <b>Download from VKontakte</b>\n\n"
            "Send me a link to:\n"
            "• Video\n"
            "• VK Video\n"
            "• Clips\n\n"
            f"{E['link']} Example: <code>https://vk.com/video-1234567_789</code>"
        ),
    },
    "download.fetching_info": {
        "ru": f"{E['search']} Получаю информацию о медиа...",
        "uz": f"{E['search']} Media haqida ma'lumot olinmoqda...",
        "en": f"{E['search']} Fetching media info...",
    },
    "download.info": {
        "ru": (
            f"{E['camera']} <b>{{title}}</b>\n\n"
            f"{E['clock']} Длительность: {{duration}}\n"
            f"{E['profile']} Автор: {{uploader}}\n\n"
            "Выбери формат:"
        ),
        "uz": (
            f"{E['camera']} <b>{{title}}</b>\n\n"
            f"{E['clock']} Davomiyligi: {{duration}}\n"
            f"{E['profile']} Muallif: {{uploader}}\n\n"
            "Formatni tanlang:"
        ),
        "en": (
            f"{E['camera']} <b>{{title}}</b>\n\n"
            f"{E['clock']} Duration: {{duration}}\n"
            f"{E['profile']} Author: {{uploader}}\n\n"
            "Choose format:"
        ),
    },
    "download.processing": {
        "ru": f"{E['clock']} Скачиваю... Подожди немного",
        "uz": f"{E['clock']} Yuklab olinmoqda... Biroz kuting",
        "en": f"{E['clock']} Downloading... Please wait",
    },
    "download.uploading": {
        "ru": f"{E['plane']} Почти готово! Загружаю файл в Telegram... Это займет пару минут {E['clock']}",
        "uz": f"{E['plane']} Deyarli tayyor! Fayl Telegramga yuklanmoqda... Bu bir necha daqiqa vaqt oladi {E['clock']}",
        "en": f"{E['plane']} Almost done! Uploading file to Telegram... This will take a couple of minutes {E['clock']}",
    },
    "download.promo": {
        "ru": f"\n\n{E['download']} Сохраняй медиа из VK бесплатно — @{{bot_username}}",
        "uz": f"\n\n{E['download']} VK'dan mediani bepul saqla — @{{bot_username}}",
        "en": f"\n\n{E['download']} Save media from VK for free — @{{bot_username}}",
    },

    # === Профиль ===
    "profile.title": {
        "ru": (
            f"{E['profile']} <b>Твой профиль</b>\n\n"
            f"{E['edit']} Имя: {{full_name}}\n"
            f"{E['info']} ID: <code>{{user_id}}</code>\n"
            f"{E['download']} Скачиваний (всего): {{downloads}}\n"
        ),
        "uz": (
            f"{E['profile']} <b>Sening profilingiz</b>\n\n"
            f"{E['edit']} Ism: {{full_name}}\n"
            f"{E['info']} ID: <code>{{user_id}}</code>\n"
            f"{E['download']} Yuklashlar (jami): {{downloads}}\n"
        ),
        "en": (
            f"{E['profile']} <b>Your profile</b>\n\n"
            f"{E['edit']} Name: {{full_name}}\n"
            f"{E['info']} ID: <code>{{user_id}}</code>\n"
            f"{E['download']} Downloads (total): {{downloads}}\n"
        ),
    },

    # === Помощь ===
    "help.text": {
        "ru": (
            f"{E['book']} <b>Помощь</b>\n\n"
            f"{E['star']} Отправь ссылку — получишь файл\n"
            f"{E['star']} Поддерживается: видео, клипы, VK Видео, фото, альбомы, посты, документы\n"
            f"{E['star']} Видео можно скачать как видео или аудио\n"
            f"{E['lock']} Закрытые профили и музыка VK не поддерживаются\n\n"
            f"{E['plane']} По вопросам: @{{admin_username}}"
        ),
        "uz": (
            f"{E['book']} <b>Yordam</b>\n\n"
            f"{E['star']} Havola yubor — faylni olasan\n"
            f"{E['star']} Qo'llab-quvvatlanadi: video, kliplar, VK Video, rasm, albomlar, postlar, hujjatlar\n"
            f"{E['star']} Videoni video yoki audio sifatida yuklab olish mumkin\n"
            f"{E['lock']} Yopiq profil va VK musiqa qo'llab-quvvatlanmaydi\n\n"
            f"{E['plane']} Savollar uchun: @{{admin_username}}"
        ),
        "en": (
            f"{E['book']} <b>Help</b>\n\n"
            f"{E['star']} Send a link — get the file\n"
            f"{E['star']} Supported: videos, clips, VK Video, photos, albums, wall posts, documents\n"
            f"{E['star']} Videos can be downloaded as video or audio\n"
            f"{E['lock']} Private profiles and VK Music are not supported\n\n"
            f"{E['plane']} Contact: @{{admin_username}}"
        ),
    },

    # === Подписка ===
    "sub.welcome": {
        "ru": (
            f"{E['bot']} <b>Привет!</b>\n\n"
            f"{E['video']} Этот бот скачивает видео и медиа "
            "из ВКонтакте — быстро и бесплатно!\n\n"
            f"{E['lock']} <b>Для начала подпишись на каналы ниже:</b>\n\n"
            f"После подписки нажми «{E['check']} Проверить подписку»"
        ),
        "uz": (
            f"{E['bot']} <b>Salom!</b>\n\n"
            f"{E['video']} Bu bot VKontakte'dan video va media "
            "yuklab oladi — tez va bepul!\n\n"
            f"{E['lock']} <b>Boshlash uchun quyidagi kanallarga obuna bo'l:</b>\n\n"
            f"Obuna bo'lgach «{E['check']} Obunani tekshirish» tugmasini bos"
        ),
        "en": (
            f"{E['bot']} <b>Hello!</b>\n\n"
            f"{E['video']} This bot downloads videos and media "
            "from VKontakte — fast and free!\n\n"
            f"{E['lock']} <b>To start, subscribe to the channels below:</b>\n\n"
            f"After subscribing, tap «{E['check']} Check subscription»"
        ),
    },
    "sub.not_subscribed": {
        "ru": (
            f"{E['cross']} <b>Ты ещё не подписался на все каналы:</b>\n\n"
            f"Подпишись и нажми «{E['check']} Проверить подписку» ещё раз."
        ),
        "uz": (
            f"{E['cross']} <b>Hali barcha kanallarga obuna bo'lmading:</b>\n\n"
            f"Obuna bo'l va «{E['check']} Obunani tekshirish» tugmasini qayta bos."
        ),
        "en": (
            f"{E['cross']} <b>You haven't subscribed to all channels yet:</b>\n\n"
            f"Subscribe and tap «{E['check']} Check subscription» again."
        ),
    },
    "sub.success": {
        "ru": (
            f"{E['check']} <b>Отлично, {{name}}!</b>\n\n"
            f"Теперь ты можешь пользоваться ботом! {E['plane']}\n\n"
            "Отправь ссылку на VK видео."
        ),
        "uz": (
            f"{E['check']} <b>Zo'r, {{name}}!</b>\n\n"
            f"Endi botdan foydalanishing mumkin! {E['plane']}\n\n"
            "VK video havolasini yubor."
        ),
        "en": (
            f"{E['check']} <b>Great, {{name}}!</b>\n\n"
            f"You can now use the bot! {E['plane']}\n\n"
            "Send a VK video link."
        ),
    },
    "btn.check_sub": {
        "ru": "Проверить подписку",
        "uz": "Obunani tekshirish",
        "en": "Check subscription",
    },
    "sub.check_alert_fail": {
        "ru": f"{E['cross']} Подпишись на все каналы!",
        "uz": f"{E['cross']} Barcha kanallarga obuna bo'ling!",
        "en": f"{E['cross']} Subscribe to all channels!",
    },
    "sub.check_alert_ok": {
        "ru": f"{E['check']} Подписка подтверждена!",
        "uz": f"{E['check']} Obuna tasdiqlandi!",
        "en": f"{E['check']} Subscription confirmed!",
    },
    "sub.not_required": {
        "ru": f"{E['check']} Подписка не требуется!",
        "uz": f"{E['check']} Obuna talab qilinmaydi!",
        "en": f"{E['check']} No subscription required!",
    },

    # === Ошибки ===
    "error.too_large": {
        "ru": f"{E['package']} <b>Файл слишком большой</b>\n\nTelegram ограничивает размер файла до 2 ГБ.",
        "uz": f"{E['package']} <b>Fayl juda katta</b>\n\nTelegram fayl hajmini 2 GB bilan cheklaydi.",
        "en": f"{E['package']} <b>File too large</b>\n\nTelegram limits file size to 2 GB.",
    },
    "error.too_large_try_lower": {
        "ru": (
            f"{E['package']} <b>Видео слишком большое</b>\n\n"
            "Файл превысил лимит 2 ГБ. Попробуй качество пониже:"
        ),
        "uz": (
            f"{E['package']} <b>Video juda katta</b>\n\n"
            "Fayl 2 GB dan oshdi. Pastroq sifatni tanlang:"
        ),
        "en": (
            f"{E['package']} <b>Video too large</b>\n\n"
            "File exceeded 2 GB limit. Try a lower quality:"
        ),
    },
    "error.generic": {
        "ru": f"{E['cross']} <b>Не удалось скачать</b>\n\nПопробуй позже или проверь ссылку.",
        "uz": f"{E['cross']} <b>Yuklab olib bo'lmadi</b>\n\nKeyinroq urinib ko'ring yoki havolani tekshiring.",
        "en": f"{E['cross']} <b>Download failed</b>\n\nTry again later or check the link.",
    },
    "error.no_access": {
        "ru": f"{E['lock']} Нет доступа",
        "uz": f"{E['lock']} Kirish yo'q",
        "en": f"{E['lock']} No access",
    },
    "error.rate_limit": {
        "ru": f"{E['clock']} <b>Слишком много запросов!</b>\n\nПодожди {{seconds}} секунд и попробуй снова.",
        "uz": f"{E['clock']} <b>Juda ko'p so'rovlar!</b>\n\n{{seconds}} soniya kuting va qayta urinib ko'ring.",
        "en": f"{E['clock']} <b>Too many requests!</b>\n\nWait {{seconds}} seconds and try again.",
    },

    # === VK-специфичные ошибки и сообщения ===
    "error.music_unsupported": {
        "ru": (
            f"{E['cross']} <b>Музыка ВК не поддерживается</b>\n\n"
            "К сожалению, официальное API аудио ВК закрыто — скачивание музыки невозможно."
        ),
        "uz": (
            f"{E['cross']} <b>VK musiqasi qo‘llab-quvvatlanmaydi</b>\n\n"
            "Afsuski, VK audio API yopiq — musiqani yuklab bo‘lmaydi."
        ),
        "en": (
            f"{E['cross']} <b>VK Music is not supported</b>\n\n"
            "Sorry, the VK Audio API is closed — downloading music is not possible."
        ),
    },
    "error.closed_profile": {
        "ru": (
            f"{E['lock']} <b>Закрытый профиль</b>\n\n"
            "Владелец страницы ограничил доступ. Скачать не получится."
        ),
        "uz": (
            f"{E['lock']} <b>Yopiq profil</b>\n\n"
            "Sahifa egasi kirishni cheklagan. Yuklab bo‘lmaydi."
        ),
        "en": (
            f"{E['lock']} <b>Private profile</b>\n\n"
            "The owner restricted access. Download is not possible."
        ),
    },
    "error.live_unsupported": {
        "ru": (
            f"{E['cross']} <b>Прямой эфир не поддерживается</b>\n\n"
            "Мы не скачиваем трансляции в реальном времени. "
            "Когда эфир закончится — попробуй ещё раз, запись можно будет сохранить."
        ),
        "uz": (
            f"{E['cross']} <b>Jonli efir qo'llab-quvvatlanmaydi</b>\n\n"
            "Real vaqtdagi translyatsiyalarni yuklab ololmaymiz. "
            "Efir tugagach qayta urinib ko'ring — yozuvni saqlash mumkin bo'ladi."
        ),
        "en": (
            f"{E['cross']} <b>Live stream is not supported</b>\n\n"
            "We don't download real-time broadcasts. "
            "Once the stream ends, try again — the recording can be saved."
        ),
    },
    "error.deleted": {
        "ru": f"{E['cross']} <b>Контент удалён</b>\n\nПубликация больше недоступна.",
        "uz": f"{E['cross']} <b>Kontent o‘chirilgan</b>\n\nNashr endi mavjud emas.",
        "en": f"{E['cross']} <b>Content deleted</b>\n\nThe post is no longer available.",
    },
    "error.story_unsupported": {
        "ru": (
            f"{E['cross']} <b>Сторис ВК не поддерживаются</b>\n\n"
            "VK не даёт скачивать истории без входа в аккаунт. "
            "Пришли ссылку на видео, клип, фото, альбом, пост или документ."
        ),
        "uz": (
            f"{E['cross']} <b>VK hikoyalari qo‘llab-quvvatlanmaydi</b>\n\n"
            "VK hikoyalarni hisobga kirmasdan yuklab olishga ruxsat bermaydi. "
            "Video, klip, rasm, albom, post yoki hujjat havolasini yuboring."
        ),
        "en": (
            f"{E['cross']} <b>VK Stories are not supported</b>\n\n"
            "VK doesn't allow downloading stories without signing in. "
            "Send a link to a video, clip, photo, album, post or document."
        ),
    },
    "error.unsupported_type": {
        "ru": (
            f"{E['cross']} <b>Тип ссылки не поддерживается</b>\n\n"
            "Мы поддерживаем: видео, клипы, фото, альбомы, посты, документы."
        ),
        "uz": (
            f"{E['cross']} <b>Havola turi qo‘llab-quvvatlanmaydi</b>\n\n"
            "Biz qo‘llab-quvvatlaymiz: video, kliplar, rasmlar, albomlar, postlar, hujjatlar."
        ),
        "en": (
            f"{E['cross']} <b>Link type not supported</b>\n\n"
            "We support: videos, clips, photos, albums, posts, documents."
        ),
    },
    "download.splitting": {
        "ru": f"{E['package']} Файл крупный — режу на части, подожди...",
        "uz": f"{E['package']} Fayl katta — qismlarga bo‘linmoqda, kuting...",
        "en": f"{E['package']} File is large — splitting into parts, please wait...",
    },
    "download.part_caption": {
        "ru": "Часть {n}/{total}",
        "uz": "Qism {n}/{total}",
        "en": "Part {n}/{total}",
    },
    "download.post_caption": {
        "ru": f"{E['pin']} Пост со стены — {{count}} вложений",
        "uz": f"{E['pin']} Devor posti — {{count}} biriktirma",
        "en": f"{E['pin']} Wall post — {{count}} attachments",
    },
    "admin.channel_deleted": {
        "ru": f"{E['check']} Канал удалён!",
        "uz": f"{E['check']} Kanal o'chirildi!",
        "en": f"{E['check']} Channel deleted!",
    },
    "admin.channel_not_found": {
        "ru": f"{E['cross']} Канал не найден",
        "uz": f"{E['cross']} Kanal topilmadi",
        "en": f"{E['cross']} Channel not found",
    },
    "admin.channel_already_exists": {
        "ru": f"{E['cross']} Канал {{channel_id}} уже добавлен",
        "uz": f"{E['cross']} Kanal {{channel_id}} allaqachon qo'shilgan",
        "en": f"{E['cross']} Channel {{channel_id}} already added",
    },
    "admin.no_broadcast_msg": {
        "ru": f"{E['cross']} Нет сообщения",
        "uz": f"{E['cross']} Xabar yo'q",
        "en": f"{E['cross']} No message",
    },
    "download.read_more": {
        "ru": f'{E["link"]} <a href="{{url}}">Читать полностью в VK</a>',
        "uz": f'{E["link"]} <a href="{{url}}">VKda to\'liq o\'qish</a>',
        "en": f'{E["link"]} <a href="{{url}}">Read full post on VK</a>',
    },
    "download.not_vk": {
        "ru": (
            f"{E['search']} Это не похоже на ссылку VK.\n\n"
            f"Отправь ссылку вида:\n"
            f"<code>https://vk.com/...</code>"
        ),
        "uz": (
            f"{E['search']} Bu VK havolasiga o'xshamaydi.\n\n"
            f"Quyidagi ko'rinishdagi havolani yuboring:\n"
            f"<code>https://vk.com/...</code>"
        ),
        "en": (
            f"{E['search']} This doesn't look like a VK link.\n\n"
            f"Send a link like:\n"
            f"<code>https://vk.com/...</code>"
        ),
    },
    "download.progress": {
        "ru": f"{E['clock']} <b>Скачиваю...</b>\n{{bar}} {{percent}}%\n{{dl}} МБ из {{total}} МБ",
        "uz": f"{E['clock']} <b>Yuklanmoqda...</b>\n{{bar}} {{percent}}%\n{{dl}} MB / {{total}} MB",
        "en": f"{E['clock']} <b>Downloading...</b>\n{{bar}} {{percent}}%\n{{dl}} MB of {{total}} MB",
    },
    "download.no_caption": {
        "ru": "Видео из ВКонтакте",
        "uz": "VKontakte'dan video",
        "en": "Video from VKontakte",
    },
    "download.cached_hit": {
        "ru": f"{E['lightning']} Из кэша — отправляю сразу",
        "uz": f"{E['lightning']} Keshdan — darhol yuborilmoqda",
        "en": f"{E['lightning']} From cache — sending now",
    },

    # === Выбор языка ===
    "lang.choose": {
        "ru": f"{E['gear']} <b>Выберите язык:</b>",
        "uz": f"{E['gear']} <b>Tilni tanlang:</b>",
        "en": f"{E['gear']} <b>Choose language:</b>",
    },
    "lang.changed": {
        "ru": f"{E['check']} Язык изменён на русский",
        "uz": f"{E['check']} Til o'zbek tiliga o'zgartirildi",
        "en": f"{E['check']} Language changed to English",
    },

    # === Админ-панель ===
    "admin.title": {
        "ru": f"{E['gear']} <b>Админ-панель</b>\n\nВыбери действие:",
        "uz": f"{E['gear']} <b>Admin panel</b>\n\nAmalni tanlang:",
        "en": f"{E['gear']} <b>Admin panel</b>\n\nChoose an action:",
    },
    "admin.no_access": {
        "ru": f"{E['lock']} У тебя нет доступа к админке.",
        "uz": f"{E['lock']} Sizda admin panelga kirish huquqi yo'q.",
        "en": f"{E['lock']} You don't have access to admin panel.",
    },
    "admin.stats": {
        "ru": (
            f"{E['chart']} <b>Статистика бота</b>\n\n"
            f"{E['users']} Всего юзеров: <b>{{total_users}}</b>\n"
            f"{E['star']} Новых юзеров сегодня: <b>{{today_users}}</b>\n"
            f"{E['download']} Всего скачиваний: <b>{{total_downloads}}</b>\n"
            f"{E['megaphone']} Каналов: <b>{{total_channels}}</b>"
        ),
        "uz": (
            f"{E['chart']} <b>Bot statistikasi</b>\n\n"
            f"{E['users']} Jami foydalanuvchilar: <b>{{total_users}}</b>\n"
            f"{E['star']} Bugungi yangi foydalanuvchilar: <b>{{today_users}}</b>\n"
            f"{E['download']} Jami yuklashlar: <b>{{total_downloads}}</b>\n"
            f"{E['megaphone']} Kanallar: <b>{{total_channels}}</b>"
        ),
        "en": (
            f"{E['chart']} <b>Bot statistics</b>\n\n"
            f"{E['users']} Total users: <b>{{total_users}}</b>\n"
            f"{E['star']} New users today: <b>{{today_users}}</b>\n"
            f"{E['download']} Total downloads: <b>{{total_downloads}}</b>\n"
            f"{E['megaphone']} Channels: <b>{{total_channels}}</b>"
        ),
    },
    "admin.channels_empty": {
        "ru": f"{E['megaphone']} <b>Каналы</b>\n\nСписок пуст. Добавь канал кнопкой ниже.",
        "uz": f"{E['megaphone']} <b>Kanallar</b>\n\nRo'yxat bo'sh. Quyidagi tugma orqali kanal qo'shing.",
        "en": f"{E['megaphone']} <b>Channels</b>\n\nList is empty. Add a channel using the button below.",
    },
    "admin.channels_title": {
        "ru": f"{E['megaphone']} <b>Каналы для подписки:</b>\n",
        "uz": f"{E['megaphone']} <b>Obuna kanallari:</b>\n",
        "en": f"{E['megaphone']} <b>Subscription channels:</b>\n",
    },
    "admin.add_channel_id": {
        "ru": (
            f"{E['megaphone']} <b>Добавление канала</b>\n\n"
            "Отправь <b>ID канала</b> (например <code>-1001234567890</code>)\n\n"
            f"{E['bulb']} Узнать ID: добавь бота @getmyid_bot в канал"
        ),
        "uz": (
            f"{E['megaphone']} <b>Kanal qo'shish</b>\n\n"
            "<b>Kanal ID</b> raqamini yuboring (masalan <code>-1001234567890</code>)\n\n"
            f"{E['bulb']} ID bilish: @getmyid_bot ni kanalga qo'shing"
        ),
        "en": (
            f"{E['megaphone']} <b>Add channel</b>\n\n"
            "Send the <b>channel ID</b> (e.g. <code>-1001234567890</code>)\n\n"
            f"{E['bulb']} Get ID: add @getmyid_bot to the channel"
        ),
    },
    "admin.add_channel_title": {
        "ru": f"{E['edit']} Теперь отправь <b>название канала</b>:",
        "uz": f"{E['edit']} Endi <b>kanal nomini</b> yuboring:",
        "en": f"{E['edit']} Now send the <b>channel name</b>:",
    },
    "admin.add_channel_link": {
        "ru": (
            f"{E['link']} Теперь отправь <b>ссылку или юзернейм канала</b>\n\n"
            "Принимаю любой формат:\n"
            "• <code>https://t.me/your_channel</code>\n"
            "• <code>@your_channel</code>\n"
            "• <code>your_channel</code>"
        ),
        "uz": (
            f"{E['link']} Endi <b>kanal havolasi yoki username</b> yuboring\n\n"
            "Istalgan formatda:\n"
            "• <code>https://t.me/your_channel</code>\n"
            "• <code>@your_channel</code>\n"
            "• <code>your_channel</code>"
        ),
        "en": (
            f"{E['link']} Now send the <b>channel link or username</b>\n\n"
            "Any format accepted:\n"
            "• <code>https://t.me/your_channel</code>\n"
            "• <code>@your_channel</code>\n"
            "• <code>your_channel</code>"
        ),
    },
    "admin.channel_added": {
        "ru": f"{E['check']} <b>Канал добавлен!</b>",
        "uz": f"{E['check']} <b>Kanal qo'shildi!</b>",
        "en": f"{E['check']} <b>Channel added!</b>",
    },
    "admin.confirm_delete": {
        "ru": f"{E['warning']} <b>Удалить канал?</b>\n\nID: <code>{{channel_id}}</code>\n\nЭто действие нельзя отменить.",
        "uz": f"{E['warning']} <b>Kanalni o'chirishni xohlaysizmi?</b>\n\nID: <code>{{channel_id}}</code>\n\nBu amalni qaytarib bo'lmaydi.",
        "en": f"{E['warning']} <b>Delete channel?</b>\n\nID: <code>{{channel_id}}</code>\n\nThis action cannot be undone.",
    },
    "admin.id_not_number": {
        "ru": f"{E['cross']} ID должен быть числом. Попробуй ещё раз:",
        "uz": f"{E['cross']} ID raqam bo'lishi kerak. Qayta urinib ko'ring:",
        "en": f"{E['cross']} ID must be a number. Try again:",
    },
    "admin.title_too_long": {
        "ru": f"{E['cross']} Название слишком длинное (макс 200 символов)",
        "uz": f"{E['cross']} Nom juda uzun (maks 200 belgi)",
        "en": f"{E['cross']} Name is too long (max 200 characters)",
    },
    "admin.link_invalid": {
        "ru": f"{E['cross']} Не удалось распознать ссылку.\nПопробуй ещё:",
        "uz": f"{E['cross']} Havolani aniqlab bo'lmadi.\nQayta urinib ko'ring:",
        "en": f"{E['cross']} Could not parse the link.\nTry again:",
    },

    # === Кнопки админки ===
    "btn.admin_stats": {"ru": "Статистика", "uz": "Statistika", "en": "Statistics"},
    "btn.admin_channels": {"ru": "Каналы", "uz": "Kanallar", "en": "Channels"},
    "btn.admin_home": {"ru": "Главное меню", "uz": "Bosh menyu", "en": "Main menu"},
    "btn.admin_add": {"ru": "Добавить канал", "uz": "Kanal qo'shish", "en": "Add channel"},
    "btn.admin_back": {"ru": "Назад", "uz": "Orqaga", "en": "Back"},
    "btn.admin_cancel": {"ru": "Отмена", "uz": "Bekor qilish", "en": "Cancel"},
    "btn.admin_confirm_del": {"ru": "Да, удалить", "uz": "Ha, o'chirish", "en": "Yes, delete"},
    "btn.admin_cancel_del": {"ru": "Отмена", "uz": "Bekor qilish", "en": "Cancel"},
    "btn.admin_panel": {"ru": "Админ-панель", "uz": "Admin panel", "en": "Admin panel"},
    "btn.admin_broadcast": {"ru": "Рассылка", "uz": "Xabar tarqatish", "en": "Broadcast"},

    # === Рассылка ===
    "admin.broadcast_prompt": {
        "ru": f"{E['plane']} <b>Массовая рассылка</b>\n\nОтправь текст/фото/видео для рассылки.\nПоддерживается HTML.",
        "uz": f"{E['plane']} <b>Ommaviy xabar</b>\n\nYuborish uchun matn/rasm/video yuboring.\nHTML qo'llab-quvvatlanadi.",
        "en": f"{E['plane']} <b>Mass broadcast</b>\n\nSend text/photo/video to broadcast.\nHTML supported.",
    },
    "admin.broadcast_preview": {
        "ru": f"{E['eye']} <b>Предпросмотр</b>\n\nОтправить это сообщение всем юзерам?",
        "uz": f"{E['eye']} <b>Oldindan ko'rish</b>\n\nBu xabarni barcha foydalanuvchilarga yuborishni xohlaysizmi?",
        "en": f"{E['eye']} <b>Preview</b>\n\nSend this message to all users?",
    },
    "admin.broadcast_confirm": {"ru": "Да, отправить", "uz": "Ha, yuborish", "en": "Yes, send"},
    "admin.broadcast_cancel": {"ru": "Отмена", "uz": "Bekor qilish", "en": "Cancel"},
    "admin.broadcast_started": {
        "ru": f"{E['plane']} Рассылка запущена... Ожидай отчёт.",
        "uz": f"{E['plane']} Xabar yuborilmoqda... Hisobotni kuting.",
        "en": f"{E['plane']} Broadcast started... Wait for report.",
    },
    "admin.broadcast_done": {
        "ru": f"{E['chart']} <b>Рассылка завершена!</b>\n\n{E['check']} Доставлено: <b>{{success}}</b>\n{E['cross']} Ошибок: <b>{{failed}}</b>\n{E['users']} Всего: <b>{{total}}</b>",
        "uz": f"{E['chart']} <b>Xabar yuborish tugadi!</b>\n\n{E['check']} Yetkazildi: <b>{{success}}</b>\n{E['cross']} Xatolar: <b>{{failed}}</b>\n{E['users']} Jami: <b>{{total}}</b>",
        "en": f"{E['chart']} <b>Broadcast complete!</b>\n\n{E['check']} Delivered: <b>{{success}}</b>\n{E['cross']} Failed: <b>{{failed}}</b>\n{E['users']} Total: <b>{{total}}</b>",
    },

    # === Описания команд бота (для меню Telegram) ===
    "cmd.start": {
        "ru": "Запустить бота",
        "uz": "Botni boshlash",
        "en": "Start the bot",
    },
    "cmd.menu": {
        "ru": "Главное меню",
        "uz": "Bosh menyu",
        "en": "Main menu",
    },
    "cmd.profile": {
        "ru": "Мой профиль",
        "uz": "Mening profilim",
        "en": "My profile",
    },
    "cmd.help": {
        "ru": "Помощь",
        "uz": "Yordam",
        "en": "Help",
    },
    "cmd.language": {
        "ru": "Сменить язык",
        "uz": "Tilni o'zgartirish",
        "en": "Change language",
    },
}


def t(key: str, lang: str = "ru", **kwargs) -> str:
    """Получить перевод по ключу и языку"""
    translations = TRANSLATIONS.get(key, {})
    text = translations.get(lang, translations.get("ru", f"[{key}]"))
    if kwargs:
        text = text.format(**kwargs)
    return text


def detect_language(language_code: str | None) -> str:
    """Определяет язык по Telegram: ru → русский, uz → узбекский, остальное → русский (дефолт)"""
    if not language_code:
        return "ru"
    if language_code.startswith("ru"):
        return "ru"
    if language_code.startswith("uz"):
        return "uz"
    if language_code.startswith("en"):
        return "en"
    return "ru"
