from blog.tags import find_tag


def test_match_ignores_case():
    assert find_tag(["Python", "Rust"], "pYTHON") == "Python"
