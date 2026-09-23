from verireview.syntax import extract_facts, parse
from verireview.syntax.facts import CodeFacts

CODE = """\
def save_user(db, username, items):
    if username is None:
        raise ValueError("username is required") from None
    elif not items:
        raise
    while len(items) == 0:
        items = load()
    assert username != ""
    label = "x" if username else "y"
    try:
        db.insert("users", {"name": username})
    except (KeyError, TypeError) as exc:
        logger.exception("failed")
        raise ServiceError("boom") from exc
    except OSError:
        pass
    except:
        ...
    return {"id": 1}, 201
"""


def facts() -> CodeFacts:
    return extract_facts(parse(CODE).root_node)


def test_calls_with_callee() -> None:
    callees = [c.callee for c in facts().calls]

    assert callees == [
        "ValueError",
        "len",
        "load",
        "db.insert",
        "logger.exception",
        "ServiceError",
    ]


def test_conditions_with_kinds_and_flags() -> None:
    got = [(c.condition_kind, c.text, c.checks_none, c.checks_empty) for c in facts().conditions]

    assert got == [
        ("if", "username is None", True, False),
        ("elif", "not items", False, True),
        ("while", "len(items) == 0", False, True),
        ("assert", 'username != ""', False, True),
        ("ternary", "username", False, False),
    ]


def test_condition_identifiers() -> None:
    first = facts().conditions[0]

    assert first.identifiers == {"username"}
    assert first.line == 2


def test_raises_ignore_cause_and_detect_bare_raise() -> None:
    assert [(r.exception, r.line) for r in facts().raises] == [
        ("ValueError", 3),
        (None, 5),
        ("ServiceError", 14),
    ]


def test_handlers() -> None:
    got = [(h.exceptions, h.swallows, h.reraises, h.text) for h in facts().handlers]

    assert got == [
        (("KeyError", "TypeError"), False, True, "except (KeyError, TypeError) as exc"),
        (("OSError",), True, False, "except OSError"),
        ((), True, False, "except"),
    ]


def test_returns() -> None:
    (ret,) = facts().returns

    assert ret.value == '{"id": 1}, 201'
    assert ret.line == 19


def test_identifiers() -> None:
    assert {"username", "db", "items", "exc", "ServiceError"} <= facts().identifiers


def test_text_is_whitespace_normalised() -> None:
    a = extract_facts(parse("if  a   is None:\n    pass\n").root_node)
    b = extract_facts(parse("if a is None:\n    pass\n").root_node)

    assert a.conditions[0].key == b.conditions[0].key


def test_none_comparison_via_double_equals() -> None:
    (cond,) = extract_facts(parse("if x == None:\n    pass\n").root_node).conditions

    assert cond.checks_none


def test_merged_combines_facts() -> None:
    a = extract_facts(parse("f()\n").root_node)
    b = extract_facts(parse("g()\n").root_node)

    assert [c.callee for c in a.merged(b).calls] == ["f", "g"]
