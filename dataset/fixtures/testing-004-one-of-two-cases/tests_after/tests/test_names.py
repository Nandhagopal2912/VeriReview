import pytest

from accounts.names import normalise_name


def test_normalises_spacing_and_case():
    assert normalise_name("  ada   lovelace ") == "Ada Lovelace"


def test_blank_name_is_rejected():
    with pytest.raises(ValueError):
        normalise_name("   ")
