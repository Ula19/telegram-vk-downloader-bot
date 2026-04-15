FROM python:3.12-slim

# ffmpeg для сплита видео (ffmpeg -c copy) и склейки DASH
# curl для диагностики
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# сначала зависимости (кэшируется Docker слоем)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# потом код
COPY bot/ bot/

# папка для cookies (опционально монтируется с хоста)
RUN mkdir -p /app/cookies

CMD ["python", "-m", "bot.main"]
