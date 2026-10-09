"""Проверки избранного. Запуск: python test_favorites.py"""
import favorites


def test_add_is_idempotent_and_remove_reports_result():
    db = favorites.connect(":memory:")
    assert favorites.add(db, 1, 550, "Бойцовский клуб", "1999-10-15")
    assert not favorites.add(db, 1, 550, "Бойцовский клуб", "1999-10-15")
    assert favorites.remove(db, 1, 550)
    assert not favorites.remove(db, 1, 550)


def test_page_shows_newest_first_and_counts_pages():
    db = favorites.connect(":memory:")
    for movie_id in range(1, favorites.PAGE_SIZE + 2):
        favorites.add(db, 1, movie_id, f"Фильм {movie_id}", "")
    first, second = favorites.page(db, 1, 1), favorites.page(db, 1, 2)
    assert first["total_pages"] == 2
    assert first["results"][0] == {"id": favorites.PAGE_SIZE + 1, "title": f"Фильм {favorites.PAGE_SIZE + 1}",
                                   "release_date": ""}
    assert [m["id"] for m in second["results"]] == [1]


def test_users_do_not_see_each_other():
    db = favorites.connect(":memory:")
    favorites.add(db, 1, 550, "Бойцовский клуб", "1999-10-15")
    assert favorites.page(db, 2, 1) == {"total_pages": 0, "results": []}
    assert not favorites.remove(db, 2, 550)


if __name__ == "__main__":
    for name, test in list(globals().items()):
        if name.startswith("test_"):
            test()
            print("ok", name)
