FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py .

# бот работает не от root; избранное лежит в /app/data — подключайте туда volume
RUN useradd --create-home bot && mkdir data && chown bot data
USER bot
VOLUME /app/data

CMD ["python", "bot.py"]
