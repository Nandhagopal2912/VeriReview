from stats.median import median


def test_empty_list_has_no_median():
    assert median([]) is None
