"""Проверки оформления карточек и выбора фильма. Запуск: python test_tmdb.py"""
import asyncio
from unittest.mock import patch

import tmdb

GENRES = {18: "драма", 80: "криминал"}


def test_card_escapes_html_and_shows_genres():
    movie = {"title": "Tom & <Jerry>", "release_date": "1994-09-23", "vote_average": 8.71,
             "genre_ids": [18, 80, 999], "overview": "Описание"}
    text = tmdb.card(movie, GENRES)
    assert text.startswith("<b>Tom &amp; &lt;Jerry&gt;</b> (1994)\n⭐ 8.7 · драма, криминал\n\n"), text


def test_card_without_date_rating_and_overview():
    movie = {"title": "Скоро", "release_date": "", "vote_average": 0, "genres": [{"id": 27, "name": "ужасы"}]}
    assert tmdb.card(movie, GENRES) == "<b>Скоро</b>\nужасы\n\nОписания пока нет."


def test_long_overview_fits_photo_caption():
    text = tmdb.card({"title": "A", "overview": "слово " * 500}, {})
    assert len(text) < 1024 and text.endswith("…"), len(text)


def test_list_text_numbers_movies():
    movies = [{"title": "A", "release_date": "2020-01-01", "vote_average": 7.5}, {"title": "B"}]
    text = tmdb.list_text("Топ", movies, page=2, total=5)
    assert "<b>Топ</b> · стр. 2 из 5" in text
    assert "1. <b>A</b> (2020) ⭐ 7.5\n2. <b>B</b>\n" in text, text


def test_recommend_returns_none_when_genre_is_empty():
    async def fake_get(path, **params):
        return {"total_pages": 0, "results": []}

    with patch.object(tmdb, "_get", fake_get):
        assert asyncio.run(tmdb.recommend(18)) is None


def test_recommend_takes_movie_from_random_page():
    pages = []

    async def fake_get(path, **params):
        pages.append(params["page"])
        return {"total_pages": 3, "results": [{"title": f"p{params['page']}"}]}

    with patch.object(tmdb, "_get", fake_get):
        movie = asyncio.run(tmdb.recommend(18))
    assert 1 <= pages[-1] <= 3 and movie["title"] == f"p{pages[-1]}"


if __name__ == "__main__":
    for name, test in list(globals().items()):
        if name.startswith("test_"):
            test()
            print("ok", name)
