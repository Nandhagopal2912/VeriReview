import pytest

from text.slug import slugify


@pytest.mark.parametrize("title", [None, ""])
def test_blank_titles_give_empty_slug(title):
    assert slugify(title) == ""
