"""Запросы к TMDB и оформление фильмов в сообщения Telegram."""
import html
import os
import random

import aiohttp

API_URL = "https://api.themoviedb.org/3"
POSTER_URL = "https://image.tmdb.org/t/p/w500"
LANGUAGE = "ru-RU"
TIMEOUT = aiohttp.ClientTimeout(total=10)
MAX_PAGE = 500  # дальше 500-й страницы TMDB не отдаёт
MIN_RATING = 7
MIN_VOTES = 200
MAX_OVERVIEW = 700  # подпись к фото в Telegram — максимум 1024 символа


class TMDBError(Exception):
    """TMDB не ответил или вернул ошибку."""


async def _get(path: str, **params) -> dict:
    headers = {"Authorization": f"Bearer {os.environ['TMDB_TOKEN']}"}
    # ponytail: сессия на каждый запрос; общая сессия, если запросов станет много
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT, headers=headers) as session:
            async with session.get(API_URL + path, params={"language": LANGUAGE, **params}) as response:
                response.raise_for_status()
                return await response.json()
    except (aiohttp.ClientError, TimeoutError) as error:
        raise TMDBError(f"{path}: {error}") from error


async def top_rated(page: int = 1) -> dict:
    return await _get("/movie/top_rated", page=page)


async def now_playing(page: int = 1) -> dict:
    return await _get("/movie/now_playing", page=page)


async def upcoming(page: int = 1) -> dict:
    return await _get("/movie/upcoming", page=page)


async def movie(movie_id: int) -> dict:
    return await _get(f"/movie/{movie_id}")


_genres: dict[int, str] = {}


async def genres() -> dict[int, str]:
    """Список жанров не меняется, поэтому загружаем его один раз."""
    global _genres
    if not _genres:
        data = await _get("/genre/movie/list")
        _genres = {genre["id"]: genre["name"] for genre in data["genres"]}
    return _genres


async def recommend(genre_id: int) -> dict | None:
    """Случайный популярный фильм жанра с хорошим рейтингом."""
    params = {"with_genres": genre_id, "sort_by": "popularity.desc",
              "vote_average.gte": MIN_RATING, "vote_count.gte": MIN_VOTES}
    first = await _get("/discover/movie", page=1, **params)
    page = random.randint(1, max(1, min(first["total_pages"], MAX_PAGE)))
    data = first if page == 1 else await _get("/discover/movie", page=page, **params)
    return random.choice(data["results"]) if data["results"] else None


def poster_url(movie: dict) -> str | None:
    path = movie.get("poster_path")
    return POSTER_URL + path if path else None


def _title(movie: dict) -> str:
    year = (movie.get("release_date") or "")[:4]
    title = f"<b>{html.escape(movie['title'])}</b>"
    return f"{title} ({year})" if year else title


def _rating(movie: dict) -> str:
    rating = movie.get("vote_average")
    return f"⭐ {rating:.1f}" if rating else ""


def _genre_names(movie: dict, genre_map: dict[int, str]) -> list[str]:
    if "genres" in movie:  # /movie/{id} отдаёт жанры объектами, списки — номерами
        return [genre["name"] for genre in movie["genres"]]
    return [genre_map[i] for i in movie.get("genre_ids", []) if i in genre_map]


def card(movie: dict, genre_map: dict[int, str]) -> str:
    overview = movie.get("overview") or "Описания пока нет."
    if len(overview) > MAX_OVERVIEW:
        overview = overview[:MAX_OVERVIEW].rsplit(" ", 1)[0] + "…"
    meta = " · ".join(filter(None, [_rating(movie), ", ".join(_genre_names(movie, genre_map))]))
    header = "\n".join(filter(None, [_title(movie), html.escape(meta)]))
    return f"{header}\n\n{html.escape(overview)}"


def list_text(title: str, movies: list[dict], page: int, total: int) -> str:
    lines = [f"{i}. {' '.join(filter(None, [_title(m), _rating(m)]))}" for i, m in enumerate(movies, 1)]
    return f"<b>{title}</b> · стр. {page} из {total}\n\n" + "\n".join(lines) + "\n\nНажмите номер, чтобы открыть фильм."
