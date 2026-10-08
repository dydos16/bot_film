"""Telegram-бот: советует фильмы, показывает топ, новинки и скорые премьеры."""
import asyncio
import logging
import os
from typing import Literal

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart, ExceptionTypeFilter
from aiogram.filters.callback_data import CallbackData
from aiogram.types import (CallbackQuery, ErrorEvent, InlineKeyboardButton, InlineKeyboardMarkup,
                           KeyboardButton, Message, ReplyKeyboardMarkup)
from dotenv import load_dotenv

import tmdb

TOP, NEW, SOON, RANDOM = "🏆 Топ", "🆕 Новинки", "📅 Скоро", "🎲 Посоветуй"
LISTS = {
    "top": ("🏆 Лучшие фильмы", tmdb.top_rated),
    "new": ("🆕 Сейчас в кино", tmdb.now_playing),
    "soon": ("📅 Скоро в кино", tmdb.upcoming),
}
BUTTON_TO_LIST = {TOP: "top", NEW: "new", SOON: "soon"}
NUMBERS_PER_ROW = 5
GENRES_PER_ROW = 3
ERROR_TEXT = "Не получилось связаться с базой фильмов, попробуйте чуть позже."

MENU = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=TOP), KeyboardButton(text=NEW)],
              [KeyboardButton(text=SOON), KeyboardButton(text=RANDOM)]],
    resize_keyboard=True,
)


class ListPage(CallbackData, prefix="list"):
    kind: Literal["top", "new", "soon"]
    page: int


class Film(CallbackData, prefix="film"):
    id: int


class Recommend(CallbackData, prefix="rec"):
    genre: int


dp = Dispatcher()


def rows(buttons: list, size: int) -> list[list]:
    return [buttons[i:i + size] for i in range(0, len(buttons), size)]


def button(text: str, data: CallbackData) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data.pack())


async def list_message(kind: str, page: int) -> tuple[str, InlineKeyboardMarkup]:
    title, fetch = LISTS[kind]
    data = await fetch(page)
    total = min(data["total_pages"], tmdb.MAX_PAGE)
    movies = data["results"]
    numbers = [button(str(i), Film(id=m["id"])) for i, m in enumerate(movies, 1)]
    nav = [button(text, ListPage(kind=kind, page=p))
           for text, p, show in (("← Назад", page - 1, page > 1), ("Далее →", page + 1, page < total)) if show]
    keyboard = [row for row in [*rows(numbers, NUMBERS_PER_ROW), nav] if row]
    return tmdb.list_text(title, movies, page, total), InlineKeyboardMarkup(inline_keyboard=keyboard)


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
        f"{SOON} — скорые премьеры",
        reply_markup=MENU,
    )


@dp.message(F.text.in_(BUTTON_TO_LIST))
async def on_list_button(message: Message) -> None:
    text, markup = await list_message(BUTTON_TO_LIST[message.text], 1)
    await message.answer(text, reply_markup=markup)


@dp.callback_query(ListPage.filter())
async def on_list_page(callback: CallbackQuery, callback_data: ListPage) -> None:
    text, markup = await list_message(callback_data.kind, callback_data.page)
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@dp.callback_query(Film.filter())
async def on_film(callback: CallbackQuery, callback_data: Film) -> None:
    await send_card(callback.message, await tmdb.movie(callback_data.id))
    await callback.answer()


@dp.message(F.text == RANDOM)
async def on_random(message: Message) -> None:
    genres = await tmdb.genres()
    buttons = [button(name.capitalize(), Recommend(genre=genre_id)) for genre_id, name in genres.items()]
    await message.answer("Выберите жанр:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows(buttons, GENRES_PER_ROW)))


@dp.callback_query(Recommend.filter())
async def on_recommend(callback: CallbackQuery, callback_data: Recommend) -> None:
    movie = await tmdb.recommend(callback_data.genre)
    await callback.answer()
    if movie is None:
        await callback.message.answer("В этом жанре ничего не нашлось 🤷")
        return
    more = InlineKeyboardMarkup(inline_keyboard=[[button("🎲 Ещё", callback_data)]])
    await send_card(callback.message, movie, more)


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
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
