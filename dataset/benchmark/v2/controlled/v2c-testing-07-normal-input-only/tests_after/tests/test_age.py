from datetime import date

from users.age import age


def test_age():
    assert age(date(2000, 1, 1), today=date(2020, 1, 1)) == 20
