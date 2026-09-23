import pytest

from verireview.syntax import enclosing_symbol, find_symbol, index_symbols, parse

CODE = '''\
import os


@decorator
def top(x):
    def inner():
        return x
    return inner


class Service:
    """Doc."""

    def save(self, user):
        return user

    @staticmethod
    def make():
        return Service()
'''


def names() -> list[tuple[str, str, int, int]]:
    return [
        (s.qualified_name, s.kind, s.start_line, s.end_line) for s in index_symbols(parse(CODE))
    ]


def test_indexes_functions_methods_classes_with_qualified_names() -> None:
    assert names() == [
        ("top", "function", 4, 8),  # range includes the decorator
        ("top.inner", "function", 6, 7),
        ("Service", "class", 11, 19),
        ("Service.save", "method", 14, 15),
        ("Service.make", "method", 17, 19),
    ]


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (1, None),
        (5, "top"),
        (7, "top.inner"),
        (12, "Service"),
        (15, "Service.save"),
        (17, "Service.make"),
    ],
)
def test_enclosing_symbol_is_innermost(line: int, expected: str | None) -> None:
    symbol = enclosing_symbol(index_symbols(parse(CODE)), line)

    assert (symbol.qualified_name if symbol else None) == expected


def test_find_symbol() -> None:
    symbols = index_symbols(parse(CODE))

    assert find_symbol(symbols, "Service.save") is not None
    assert find_symbol(symbols, "save") is None


@pytest.mark.parametrize(
    "code",
    [
        "def broken(:\n    pass\n",
        "class\n",
        "if x\n    y = (\n",
        "def f():\n\treturn 1\n  return 2\n",
        "\x00\x01 garbage ))) def",
        "",
        "é = 'ünïcode' # ☃\n",
    ],
)
def test_invalid_or_odd_code_never_crashes(code: str) -> None:
    tree = parse(code)

    index_symbols(tree)  # must not raise


def test_syntax_errors_are_flagged_not_raised() -> None:
    assert parse("def broken(:\n    pass\n").root_node.has_error
    assert not parse("def fine():\n    pass\n").root_node.has_error
