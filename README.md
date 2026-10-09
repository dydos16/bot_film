# bot_film

Telegram-бот, который помогает выбрать фильм. Данные берутся из [TMDB](https://www.themoviedb.org/) на русском языке.

- 🎲 **Посоветуй** — выбираете жанр, бот присылает случайный хороший фильм (рейтинг от 7, от 200 оценок). Кнопка «Ещё» — следующий.
- 🏆 **Топ** — лучшие фильмы всех времён.
- 🆕 **Новинки** — что сейчас идёт в кино.
- 📅 **Скоро** — ближайшие премьеры.
- ⭐ **Избранное** — фильмы, отложенные «посмотреть позже». Хранится в SQLite, у каждого пользователя своё.

В списках — листание кнопками ← →, по номеру открывается карточка с постером и описанием.
Под карточкой — кнопка «⭐ В избранное» / «✖ Убрать из избранного».

## Ключи

1. **Токен бота** — напишите [@BotFather](https://t.me/BotFather) команду `/newbot`.
2. **Токен TMDB** — зарегистрируйтесь на themoviedb.org → Настройки → API → создайте ключ и скопируйте
   **«API Read Access Token»** (длинный токен, не короткий «API Key»).

## Запуск

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # впишите оба токена в .env
.venv/bin/python bot.py
```

Файл `.env` в git не попадает — токены не публикуйте. Избранное сохраняется в `data/favorites.db`.

## Запуск в Docker

```bash
docker build -t bot_film .
docker run -d --name bot_film --restart unless-stopped --env-file .env -v bot_film_data:/app/data bot_film
```

Бот в контейнере работает не от root. Избранное лежит в volume `bot_film_data` и не пропадает при пересборке образа.

## Проверка

```bash
.venv/bin/python test_tmdb.py
.venv/bin/python test_favorites.py
```

## Файлы

- `bot.py` — меню, кнопки, обработчики Telegram.
- `tmdb.py` — запросы к TMDB и оформление карточек.
- `favorites.py` — избранное в SQLite.
- `test_tmdb.py` — проверки оформления и выбора фильма.
- `test_favorites.py` — проверки избранного.
- `Dockerfile` — образ для запуска на сервере.

## Идеи на потом

- Поиск по названию.
- «Похожие фильмы» (`/movie/{id}/recommendations`).
- Рассылка о новинках по расписанию.
