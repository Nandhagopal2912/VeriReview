from verireview.syntax import diff_facts, extract_facts, parse, structural_tokens


def tokens(code: str) -> tuple[str, ...]:
    return structural_tokens(parse(code).root_node)


BASE = 'def f(x):\n    """Doc."""\n    return x + 1\n'


def test_comments_are_ignored() -> None:
    assert tokens(BASE) == tokens(
        'def f(x):\n    """Doc."""\n    # a comment\n    return x + 1  # hi\n'
    )


def test_docstrings_are_ignored() -> None:
    assert tokens(BASE) == tokens(
        'def f(x):\n    """Completely different doc."""\n    return x + 1\n'
    )
    assert tokens(BASE) == tokens("def f(x):\n    return x + 1\n")


def test_module_and_class_docstrings_are_ignored() -> None:
    assert tokens('"""Module doc."""\nclass A:\n    """A."""\n    x = 1\n') == tokens(
        "class A:\n    x = 1\n"
    )


def test_formatting_is_ignored() -> None:
    assert tokens(BASE) == tokens('def f( x ):\n    """Doc."""\n    return x+1\n')


def test_non_docstring_strings_count() -> None:
    assert tokens('x = "a"\n') != tokens('x = "b"\n')


def test_second_string_statement_is_code_not_docstring() -> None:
    assert tokens('def f():\n    """Doc."""\n    "x"\n') != tokens(
        'def f():\n    """Doc."""\n    "y"\n'
    )


def test_code_change_is_detected() -> None:
    assert tokens(BASE) != tokens('def f(x):\n    """Doc."""\n    return x + 2\n')


def test_diff_facts_reports_added_and_removed() -> None:
    before = extract_facts(parse("def f(x):\n    g(x)\n    return x\n").root_node)
    after = extract_facts(
        parse("def f(x):\n    if x is None:\n        raise ValueError\n    return x\n").root_node
    )

    diff = diff_facts(before, after)

    assert [(f.kind, f.text) for f in diff.added] == [
        ("condition", "x is None"),
        ("raise", "raise ValueError"),
    ]
    assert [(f.kind, f.text) for f in diff.removed] == [("call", "g(x)")]


def test_moved_code_is_not_a_change() -> None:
    before = extract_facts(parse("a()\nb()\n").root_node)
    after = extract_facts(parse("b()\na()\n").root_node)

    assert diff_facts(before, after).empty


def test_duplicate_facts_are_counted() -> None:
    before = extract_facts(parse("a()\n").root_node)
    after = extract_facts(parse("a()\na()\n").root_node)

    diff = diff_facts(before, after)

    assert [(f.text, f.line) for f in diff.added] == [("a()", 1)]
