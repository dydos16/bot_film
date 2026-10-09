"""Telegram-бот: советует фильмы, показывает топ, новинки, скорые премьеры и избранное."""
import asyncio
import logging
import os
import sqlite3
from contextlib import closing
from typing import Literal

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart, ExceptionTypeFilter
from aiogram.filters.callback_data import CallbackData
from aiogram.types import (CallbackQuery, ErrorEvent, InlineKeyboardButton, InlineKeyboardMarkup,
                           KeyboardButton, Message, ReplyKeyboardMarkup)
from dotenv import load_dotenv

import favorites
import tmdb

TOP, NEW, SOON, RANDOM, FAVORITES = "🏆 Топ", "🆕 Новинки", "📅 Скоро", "🎲 Посоветуй", "⭐ Избранное"
LISTS = {
    "top": ("🏆 Лучшие фильмы", tmdb.top_rated),
    "new": ("🆕 Сейчас в кино", tmdb.now_playing),
    "soon": ("📅 Скоро в кино", tmdb.upcoming),
}
BUTTON_TO_LIST = {TOP: "top", NEW: "new", SOON: "soon", FAVORITES: "fav"}
NUMBERS_PER_ROW = 5
GENRES_PER_ROW = 3
ERROR_TEXT = "Не получилось связаться с базой фильмов, попробуйте чуть позже."
EMPTY_FAVORITES = "В избранном пока пусто. Откройте фильм и нажмите «⭐ В избранное»."

MENU = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=TOP), KeyboardButton(text=NEW)],
              [KeyboardButton(text=SOON), KeyboardButton(text=RANDOM)],
              [KeyboardButton(text=FAVORITES)]],
    resize_keyboard=True,
)


class ListPage(CallbackData, prefix="list"):
    kind: Literal["top", "new", "soon", "fav"]
    page: int


class Film(CallbackData, prefix="film"):
    id: int


class Recommend(CallbackData, prefix="rec"):
    genre: int


class Favorite(CallbackData, prefix="fav"):
    id: int
    genre: int = 0  # жанр «🎲 Ещё» под карточкой из «Посоветуй»; 0 — карточка из списка


dp = Dispatcher()


def rows(buttons: list, size: int) -> list[list]:
    return [buttons[i:i + size] for i in range(0, len(buttons), size)]


def button(text: str, data: CallbackData) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data.pack())


async def list_message(kind: str, page: int, user_id: int,
                       db: sqlite3.Connection) -> tuple[str, InlineKeyboardMarkup | None]:
    if kind == "fav":
        title, data = FAVORITES, favorites.page(db, user_id, page)
        if not data["results"]:
            return EMPTY_FAVORITES, None
    else:
        title, fetch = LISTS[kind]
        data = await fetch(page)
    total = min(data["total_pages"], tmdb.MAX_PAGE)
    movies = data["results"]
    numbers = [button(str(i), Film(id=m["id"])) for i, m in enumerate(movies, 1)]
    nav = [button(text, ListPage(kind=kind, page=p))
           for text, p, show in (("← Назад", page - 1, page > 1), ("Далее →", page + 1, page < total)) if show]
    keyboard = [row for row in [*rows(numbers, NUMBERS_PER_ROW), nav] if row]
    return tmdb.list_text(title, movies, page, total), InlineKeyboardMarkup(inline_keyboard=keyboard)


def card_markup(db: sqlite3.Connection, user_id: int, movie_id: int, genre: int = 0) -> InlineKeyboardMarkup:
    saved = favorites.contains(db, user_id, movie_id)
    keyboard = [[button("✖ Убрать из избранного" if saved else "⭐ В избранное", Favorite(id=movie_id, genre=genre))]]
    if genre:
        keyboard.append([button("🎲 Ещё", Recommend(genre=genre))])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def send_card(message: Message, movie: dict, markup: InlineKeyboardMarkup | None = None) -> None:
    text = tmdb.card(movie, await tmdb.genres())
    poster = tmdb.poster_url(movie)
    if poster:
        try:
            await message.answer_photo(poster, caption=text, reply_markup=markup)
            return
        except TelegramBadRequest as error:
            logging.warning("Постер %s не загрузился: %s", poster, error)
    await message.answer(text, reply_markup=markup)


@dp.message(CommandStart())
async def on_start(message: Message) -> None:
    await message.answer(
        "Привет! Я помогу выбрать, что посмотреть.\n\n"
        f"{RANDOM} — случайный хороший фильм выбранного жанра\n"
        f"{TOP} — лучшие фильмы всех времён\n"
        f"{NEW} — что сейчас идёт в кино\n"
        f"{SOON} — скорые премьеры\n"
        f"{FAVORITES} — фильмы, которые вы отложили на потом",
        reply_markup=MENU,
    )


@dp.message(F.text.in_(BUTTON_TO_LIST))
async def on_list_button(message: Message, db: sqlite3.Connection) -> None:
    text, markup = await list_message(BUTTON_TO_LIST[message.text], 1, message.from_user.id, db)
    await message.answer(text, reply_markup=markup)


@dp.callback_query(ListPage.filter())
async def on_list_page(callback: CallbackQuery, callback_data: ListPage, db: sqlite3.Connection) -> None:
    text, markup = await list_message(callback_data.kind, callback_data.page, callback.from_user.id, db)
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@dp.callback_query(Film.filter())
async def on_film(callback: CallbackQuery, callback_data: Film, db: sqlite3.Connection) -> None:
    markup = card_markup(db, callback.from_user.id, callback_data.id)
    await send_card(callback.message, await tmdb.movie(callback_data.id), markup)
    await callback.answer()


@dp.callback_query(Favorite.filter())
async def on_favorite(callback: CallbackQuery, callback_data: Favorite, db: sqlite3.Connection) -> None:
    user_id, movie_id = callback.from_user.id, callback_data.id
    if favorites.remove(db, user_id, movie_id):
        note = "Убрано из избранного"
    else:
        # в кнопку название не влезет (лимит 64 байта), поэтому берём его из TMDB
        movie = await tmdb.movie(movie_id)
        favorites.add(db, user_id, movie_id, movie["title"], movie.get("release_date") or "")
        note = "Добавлено в избранное ⭐"
    await callback.message.edit_reply_markup(reply_markup=card_markup(db, user_id, movie_id, callback_data.genre))
    await callback.answer(note)


@dp.message(F.text == RANDOM)
async def on_random(message: Message) -> None:
    genres = await tmdb.genres()
    buttons = [button(name.capitalize(), Recommend(genre=genre_id)) for genre_id, name in genres.items()]
    await message.answer("Выберите жанр:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows(buttons, GENRES_PER_ROW)))


@dp.callback_query(Recommend.filter())
async def on_recommend(callback: CallbackQuery, callback_data: Recommend, db: sqlite3.Connection) -> None:
    movie = await tmdb.recommend(callback_data.genre)
    await callback.answer()
    if movie is None:
        await callback.message.answer("В этом жанре ничего не нашлось 🤷")
        return
    await send_card(callback.message, movie, card_markup(db, callback.from_user.id, movie["id"], callback_data.genre))


@dp.error(ExceptionTypeFilter(tmdb.TMDBError))
async def on_tmdb_error(event: ErrorEvent) -> None:
    logging.warning("TMDB: %s", event.exception)
    update = event.update
    if update.callback_query:
        await update.callback_query.answer(ERROR_TEXT, show_alert=True)
    elif update.message:
        await update.message.answer(ERROR_TEXT)


async def main() -> None:
    load_dotenv()
    missing = [name for name in ("BOT_TOKEN", "TMDB_TOKEN") if not os.getenv(name)]
    if missing:
        raise SystemExit(f"Заполните в файле .env: {', '.join(missing)}")
    logging.basicConfig(level=logging.INFO)
    bot = Bot(os.environ["BOT_TOKEN"], default=DefaultBotProperties(parse_mode="HTML"))
    # aiogram передаёт db во все обработчики, где есть параметр с таким именем
    with closing(favorites.connect()) as db:
        await dp.start_polling(bot, db=db)


if __name__ == "__main__":
    asyncio.run(main())
