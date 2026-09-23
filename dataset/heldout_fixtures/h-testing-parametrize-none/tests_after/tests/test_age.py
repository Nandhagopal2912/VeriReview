import pytest

from people.age import parse_age


@pytest.mark.parametrize("value", [None])
def test_parse_age_rejects_missing(value):
    with pytest.raises(ValueError):
        parse_age(value)
