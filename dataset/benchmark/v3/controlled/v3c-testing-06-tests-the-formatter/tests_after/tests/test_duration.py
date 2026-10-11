from timeutil.duration import format_duration


def test_negative_duration():
    assert format_duration(-5) == "-5s"
