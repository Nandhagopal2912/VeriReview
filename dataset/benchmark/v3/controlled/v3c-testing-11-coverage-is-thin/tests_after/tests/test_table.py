from report.table import render_row


def test_render_row():
    assert render_row([1, 2], width=2) == "1  | 2 "
