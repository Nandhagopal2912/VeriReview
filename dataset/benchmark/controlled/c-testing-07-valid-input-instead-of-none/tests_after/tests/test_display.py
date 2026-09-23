from types import SimpleNamespace

from accounts.display import display_name


def test_display_name():
    assert display_name(SimpleNamespace(name="Ada")) == "Ada"
