from pricing.calc import calculate_tax


def test_calculate_tax_full_rate():
    assert calculate_tax(100, 1.0) == 100
