from accounts.names import normalise_name


def test_normalises_spacing_and_case():
    assert normalise_name("  ada   lovelace ") == "Ada Lovelace"
