"""Validation rule, Phase 10.1: bounds, plural names, checks in other methods, pydantic models."""

from helpers.rules import kinds, req, run_rule
from verireview.contracts import RequirementCategory as C
from verireview.rules import RuleOutcome
from verireview.rules import RuleStatus as S


def run(description: str, before: str, after: str, anchor: int = 2) -> RuleOutcome:
    return run_rule(req(C.VALIDATION, description), before, after, anchor=anchor)


ORDER = 'def order(sku, quantity):\n    return {"sku": sku, "quantity": quantity}\n'


def guarded(condition: str) -> str:
    return (
        f"def order(sku, quantity):\n    if {condition}:\n        raise ValueError('bad')\n"
        '    return {"sku": sku, "quantity": quantity}\n'
    )


# ---------------------------------------------------------------- bounds


def test_positive_at_least_one() -> None:
    assert run("`quantity` must be at least 1", ORDER, guarded("quantity < 1")).status == (
        S.SATISFIED
    )
    assert run("`quantity` must be at least 1", ORDER, guarded("quantity <= 0")).status == (
        S.SATISFIED
    )


def test_adversarial_off_by_one_bound() -> None:
    outcome = run("`quantity` must be at least 1", ORDER, guarded("quantity < 0"))

    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["validation.wrong_bound"] is False


def test_positive_means_zero_is_rejected() -> None:
    assert run("`quantity` must be positive", ORDER, guarded("quantity <= 0")).status == (
        S.SATISFIED
    )
    assert run("`quantity` must be positive", ORDER, guarded("quantity < 0")).status == (
        S.NOT_SATISFIED
    )


def test_between_needs_both_bounds() -> None:
    good = guarded("not 1 <= quantity <= 100")
    bad = guarded("quantity < 0 or quantity > 100")

    assert run("`quantity` must be between 1 and 100", ORDER, good).status == S.SATISFIED
    assert run("`quantity` must be between 1 and 100", ORDER, bad).status == S.NOT_SATISFIED


# ---------------------------------------------------------------- plural names


def test_plural_word_finds_the_singular_variable() -> None:
    before = "def set_age(p, age):\n    p.age = age\n"
    after = (
        "def set_age(p, age):\n    if age < 0:\n        raise ValueError('neg')\n    p.age = age\n"
    )

    assert run("Reject negative ages here", before, after).status == S.SATISFIED


# ---------------------------------------------------------------- check in another method

CONFIG = "from dataclasses import dataclass\n\n\n@dataclass\nclass Server:\n    port: int\n"


def test_positive_post_init_is_not_too_late_for_a_field() -> None:
    after = CONFIG + (
        "\n    def __post_init__(self):\n        if not 1 <= self.port <= 65535:\n"
        "            raise ValueError('port')\n"
    )
    assert run("Validate that `port` is between 1 and 65535", CONFIG, after, 6).status == (
        S.SATISFIED
    )


def test_negative_check_after_use_in_the_same_function() -> None:
    before = "def send(port, data):\n    connect(port).send(data)\n"
    after = (
        "def send(port, data):\n    connect(port).send(data)\n    if port < 1:\n"
        "        raise ValueError('port')\n"
    )
    outcome = run("Validate that `port` is at least 1", before, after)

    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["validation.check_after_operation"] is False


# ---------------------------------------------------------------- pydantic models

CHARGE = "def charge(gateway, card, amount):\n    return gateway.charge(card, amount)\n"


def test_positive_constrained_pydantic_field() -> None:
    after = (
        "from pydantic import BaseModel, Field\n\n\nclass Req(BaseModel):\n"
        "    amount: float = Field(gt=0)\n\n\n"
        "def charge(gateway, card, amount):\n    Req(amount=amount)\n"
        "    return gateway.charge(card, amount)\n"
    )
    outcome = run("Validate that `amount` is positive before charging", CHARGE, after, 9)

    assert outcome.status == S.SATISFIED
    assert kinds(outcome)["validation.checked_by_model"] is True


def test_adversarial_unconstrained_model_is_no_check() -> None:
    after = (
        "from pydantic import BaseModel\n\n\nclass Req(BaseModel):\n    amount: float\n\n\n"
        "def charge(gateway, card, amount):\n    Req(amount=amount)\n"
        "    return gateway.charge(card, amount)\n"
    )
    outcome = run("Validate that `amount` is positive before charging", CHARGE, after, 9)

    assert outcome.status == S.NOT_SATISFIED


def test_positive_field_validator() -> None:
    after = (
        "from pydantic import BaseModel, field_validator\n\n\nclass Req(BaseModel):\n"
        "    amount: float\n\n    @field_validator('amount')\n    def pos(cls, v):\n"
        "        return v\n\n\n"
        "def charge(gateway, card, amount):\n    Req(amount=amount)\n"
        "    return gateway.charge(card, amount)\n"
    )
    outcome = run("Validate that `amount` is positive before charging", CHARGE, after, 13)

    assert outcome.status == S.SATISFIED
