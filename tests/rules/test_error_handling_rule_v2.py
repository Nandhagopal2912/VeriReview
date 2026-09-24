"""Error-handling rule, Phase 10.1 checks: positive, negative and adversarial cases each."""

from helpers.rules import kinds, req, run_rule
from verireview.contracts import RequirementCategory as C
from verireview.rules import RuleOutcome
from verireview.rules import RuleStatus as S


def run(description: str, before: str, after: str, comment: str | None = None) -> RuleOutcome:
    return run_rule(req(C.ERROR_HANDLING, description), before, after, anchor=2, comment=comment)


LOOKUP = "def setting(s, name, default):\n    return s[name]\n"


# ---------------------------------------------------------------- bare re-raise


def test_positive_handler_returns_the_default() -> None:
    after = (
        "def setting(s, name, default):\n    try:\n        return s[name]\n"
        "    except KeyError:\n        return default\n"
    )
    assert run("Handle the KeyError", LOOKUP, after).status == S.SATISFIED


def test_adversarial_handler_that_only_reraises_handles_nothing() -> None:
    after = (
        "def setting(s, name, default):\n    try:\n        return s[name]\n"
        "    except KeyError:\n        raise\n"
    )
    outcome = run("Handle the KeyError by returning the default value", LOOKUP, after)

    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["error_handling.catch_KeyError"] is False


def test_descriptive_raises_means_catch_it() -> None:
    wrong = (
        "def setting(s, name, default):\n    try:\n        return s[name]\n"
        "    except ValueError:\n        return default\n"
    )
    comment = "`s[name]` raises KeyError for unknown names; handle that."
    outcome = run("handle that", LOOKUP, wrong, comment=comment)

    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["error_handling.catch_KeyError"] is False


# ---------------------------------------------------------------- only the named exception

LOOP = "def load(rows, parse):\n    return [parse(r) for r in rows]\n"


def test_positive_only_the_named_exception_is_caught() -> None:
    after = (
        "def load(rows, parse):\n    out = []\n    for r in rows:\n        try:\n"
        "            out.append(parse(r))\n        except ValueError:\n            continue\n"
        "    return out\n"
    )
    assert run("Catch only `ValueError`; other errors should propagate", LOOP, after).status == (
        S.SATISFIED
    )


def test_adversarial_broad_handler_kept_next_to_the_narrow_one() -> None:
    after = (
        "def load(rows, parse):\n    out = []\n    for r in rows:\n        try:\n"
        "            out.append(parse(r))\n        except ValueError:\n            continue\n"
        "        except Exception:\n            continue\n    return out\n"
    )
    outcome = run("Catch only `ValueError`; other errors should propagate", LOOP, after)

    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["error_handling.only_the_named_exception"] is False


# ---------------------------------------------------------------- chaining

CONVERT = (
    "def load(p):\n    try:\n        return parse(p)\n    except OSError as err:\n"
    "        raise ConfigError(str(err))\n"
)


def test_positive_raise_from_err() -> None:
    after = CONVERT.replace("(str(err))", "(str(err)) from err")
    assert run("Use `raise ... from err` to keep the traceback", CONVERT, after).status == (
        S.SATISFIED
    )


def test_negative_raise_without_cause() -> None:
    outcome = run("Use `raise ... from err` to keep the traceback", CONVERT, CONVERT)

    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["error_handling.chain"] is False


def test_adversarial_from_none_hides_the_cause() -> None:
    after = CONVERT.replace("(str(err))", "(str(err)) from None")
    assert run("Use `raise ... from err` to keep the traceback", CONVERT, after).status == (
        S.NOT_SATISFIED
    )


# ---------------------------------------------------------------- swallowing and traceback

SWALLOW = (
    "import logging\nlogger = logging.getLogger()\n\n\ndef rm(store, key):\n    try:\n"
    "        store.delete(key)\n    except Exception:\n        pass\n"
)


def test_positive_not_swallowed_and_logged_with_traceback() -> None:
    after = SWALLOW.replace("pass", "logger.exception('could not delete %s', key)")
    assert run("Don't swallow this silently", SWALLOW, after).status == S.SATISFIED
    assert run("log it with the traceback", SWALLOW, after).status == S.SATISFIED


def test_negative_still_swallowed() -> None:
    outcome = run("Don't swallow this silently", SWALLOW, SWALLOW)

    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["error_handling.not_swallowed"] is False


def test_adversarial_log_without_the_traceback() -> None:
    after = SWALLOW.replace("pass", "logger.warning('could not delete %s', key)")
    outcome = run("log it with the traceback", SWALLOW, after)

    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["error_handling.log"] is False


# ---------------------------------------------------------------- cleanup

LOCK = (
    "def write(lock, store, rec):\n    lock.acquire()\n    store.write(rec)\n    lock.release()\n"
)


def test_positive_release_in_finally() -> None:
    after = (
        "def write(lock, store, rec):\n    lock.acquire()\n    try:\n        store.write(rec)\n"
        "    finally:\n        lock.release()\n"
    )
    assert run("Make sure the lock is released even if the write fails", LOCK, after).status == (
        S.SATISFIED
    )


def test_positive_with_block_closes_the_file() -> None:
    before = "def rows(p):\n    f = open(p)\n    return list(f)\n"
    after = "def rows(p):\n    with open(p) as f:\n        return list(f)\n"
    assert run("Make sure the file gets closed", before, after).status == S.SATISFIED


def test_negative_release_only_on_success() -> None:
    outcome = run("Make sure the lock is released even if the write fails", LOCK, LOCK)

    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["error_handling.cleanup"] is False


# ---------------------------------------------------------------- suppress and delegation

REMOVE = "import os\n\n\ndef clear(path):\n    os.remove(path)\n"


def test_positive_suppress_is_how_to_ignore() -> None:
    after = (
        "import contextlib\nimport os\n\n\ndef clear(path):\n"
        "    with contextlib.suppress(FileNotFoundError):\n        os.remove(path)\n"
    )
    assert run("Ignore a missing file instead of crashing", REMOVE, after).status == S.SATISFIED


def test_adversarial_suppress_is_not_handling_when_handling_is_asked() -> None:
    after = (
        "import contextlib\nimport os\n\n\ndef clear(path):\n"
        "    with contextlib.suppress(OSError):\n        os.remove(path)\n"
    )
    outcome = run("Handle the `OSError` and log it", REMOVE, after)

    assert outcome.status == S.NOT_SATISFIED


def test_context_manager_defined_elsewhere_is_inconclusive() -> None:
    before = "def save(db, order):\n    db.insert(order)\n"
    after = (
        "from resilience import db_guard\n\n\ndef save(db, order):\n    with db_guard():\n"
        "        db.insert(order)\n"
    )
    outcome = run("Handle the case where the database is down", before, after)

    assert outcome.status == S.INCONCLUSIVE


# ---------------------------------------------------------------- the named call is protected

FETCH = "import requests\n\n\ndef fetch(u):\n    r = requests.get(u)\n    return r.json()\n"


def test_positive_handler_around_the_named_call() -> None:
    after = (
        "import requests\n\n\ndef fetch(u):\n    try:\n        r = requests.get(u)\n"
        "    except requests.RequestException:\n        return {}\n    return r.json()\n"
    )
    comment = "`requests.get` can raise `RequestException`; catch it and return an empty dict."
    outcome = run("catch it and return an empty dict", FETCH, after, comment=comment)

    assert outcome.status == S.SATISFIED


def test_adversarial_handler_around_another_call() -> None:
    after = (
        "import requests\n\n\ndef fetch(u):\n    r = requests.get(u)\n    try:\n"
        "        return r.json()\n    except requests.RequestException:\n        return {}\n"
    )
    comment = "`requests.get` can raise `RequestException`; catch it and return an empty dict."
    outcome = run("catch it and return an empty dict", FETCH, after, comment=comment)

    assert outcome.status == S.NOT_SATISFIED
