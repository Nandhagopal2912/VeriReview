"""API rule, Phase 10.1: status names, raised HTTP exceptions, except branches, dead code,
absence polarity, unconditional requests, message content and return values."""

from helpers.rules import kinds, req, run_rule
from verireview.contracts import RequirementCategory as C
from verireview.rules import RuleOutcome
from verireview.rules import RuleStatus as S

HEAD = "from flask import Flask, abort, jsonify, request\n\napp = Flask(__name__)\n\n\n"
RATE = HEAD + '@app.post("/rate")\ndef rate():\n    stars = request.json.get("stars")\n'


def run(description: str, before: str, after: str, anchor: int = 8) -> RuleOutcome:
    return run_rule(req(C.API_BEHAVIOR, description), before, after, anchor=anchor)


BEFORE = RATE + "    return jsonify({'stars': stars})\n"
WANT_400 = "Return 400 if `stars` is not between 1 and 5"


# ---------------------------------------------------------------- status names


def test_positive_httpstatus_enum_counts_as_400() -> None:
    after = (
        "from http import HTTPStatus\n"
        + RATE
        + "    if not 1 <= stars <= 5:\n        return jsonify({}), HTTPStatus.BAD_REQUEST\n"
        "    return jsonify({'stars': stars})\n"
    )
    assert run(WANT_400, BEFORE, after, anchor=9).status == S.SATISFIED


def test_positive_drf_status_constant() -> None:
    after = RATE + (
        "    if not 1 <= stars <= 5:\n"
        "        return Response({}, status=status.HTTP_400_BAD_REQUEST)\n"
        "    return jsonify({'stars': stars})\n"
    )
    assert run(WANT_400, BEFORE, after).status == S.SATISFIED


def test_adversarial_other_status_name_is_not_400() -> None:
    after = (
        "from http import HTTPStatus\n"
        + RATE
        + "    if not 1 <= stars <= 5:\n        return jsonify({}), HTTPStatus.NOT_FOUND\n"
        "    return jsonify({'stars': stars})\n"
    )
    assert run(WANT_400, BEFORE, after, anchor=9).status == S.NOT_SATISFIED


# ---------------------------------------------------------------- unreachable code


def test_adversarial_abort_after_return_never_runs() -> None:
    after = BEFORE + "    if not 1 <= stars <= 5:\n        abort(400)\n"
    outcome = run(WANT_400, BEFORE, after)

    assert outcome.status == S.NOT_SATISFIED


def test_positive_abort_before_return() -> None:
    after = RATE + "    if not 1 <= stars <= 5:\n        abort(400)\n    return jsonify({})\n"
    assert run(WANT_400, BEFORE, after).status == S.SATISFIED


# ---------------------------------------------------------------- raised HTTP exceptions

TICKET = HEAD + (
    "TICKETS = {}\n\n\nclass TicketNotFound(Exception):\n    pass\n\n\n"
    "@app.errorhandler(TicketNotFound)\ndef not_found(error):\n"
    "    return jsonify({'error': 'no ticket'}), 404\n\n\n"
    '@app.get("/tickets/<int:ticket_id>")\ndef ticket(ticket_id):\n'
)


def test_positive_custom_exception_mapped_by_errorhandler() -> None:
    before = TICKET + "    return jsonify(TICKETS[ticket_id])\n"
    after = TICKET + (
        "    if ticket_id not in TICKETS:\n        raise TicketNotFound()\n"
        "    return jsonify(TICKETS[ticket_id])\n"
    )
    outcome = run("Return 404 when the ticket doesn't exist", before, after, anchor=21)
    assert outcome.status == S.SATISFIED


def test_negative_unmapped_exception_is_not_a_status() -> None:
    before = TICKET + "    return jsonify(TICKETS[ticket_id])\n"
    after = TICKET + (
        "    if ticket_id not in TICKETS:\n        raise KeyError(ticket_id)\n"
        "    return jsonify(TICKETS[ticket_id])\n"
    )
    outcome = run("Return 404 when the ticket doesn't exist", before, after, anchor=21)
    assert outcome.status == S.NOT_SATISFIED


def test_positive_django_http404() -> None:
    before = "def detail(request, pk):\n    return render(request, 'x', {'o': OBJS[pk]})\n"
    after = (
        "def detail(request, pk):\n    if pk not in OBJS:\n        raise Http404('no object')\n"
        "    return render(request, 'x', {'o': OBJS[pk]})\n"
    )
    assert run("Return 404 when the object is missing", before, after, anchor=2).status == (
        S.SATISFIED
    )


# ---------------------------------------------------------------- except branches

PARSE = (
    "import json\n\n\ndef create(request):\n    data = json.loads(request.body)\n"
    "    return JsonResponse({'id': data['id']}, status=201)\n"
)


def test_positive_status_in_except_branch_for_invalid_json() -> None:
    after = (
        "import json\n\n\ndef create(request):\n    try:\n        data = json.loads(request.body)\n"
        "    except json.JSONDecodeError:\n        return JsonResponse({'e': 'bad'}, status=400)\n"
        "    return JsonResponse({'id': data['id']}, status=201)\n"
    )
    outcome = run("Invalid JSON should give a 400, not a 500", PARSE, after, anchor=5)
    assert outcome.status == S.SATISFIED


def test_negative_no_400_anywhere() -> None:
    outcome = run("Invalid JSON should give a 400, not a 500", PARSE, PARSE, anchor=5)
    assert outcome.status == S.NOT_SATISFIED


# ---------------------------------------------------------------- absence polarity

PROFILE = HEAD + '@app.get("/p/<name>")\ndef profile(name):\n    user = PROFILES.get(name)\n'


def test_positive_404_on_absent_branch() -> None:
    before = PROFILE + "    return jsonify(user)\n"
    after = PROFILE + (
        "    if user is None:\n        return jsonify({}), 404\n    return jsonify(user)\n"
    )
    assert run("Return 404 when the user is not found", before, after).status == S.SATISFIED


def test_positive_404_in_else_of_presence_check() -> None:
    before = PROFILE + "    return jsonify(user)\n"
    after = PROFILE + (
        "    if user:\n        return jsonify(user)\n    else:\n        return jsonify({}), 404\n"
    )
    assert run("Return 404 when the user is not found", before, after).status == S.SATISFIED


def test_adversarial_404_on_the_found_branch() -> None:
    before = PROFILE + "    return jsonify(user)\n"
    after = PROFILE + "    if user:\n        return jsonify({}), 404\n    return jsonify(user)\n"
    assert run("Return 404 when the user is not found", before, after).status == (S.NOT_SATISFIED)


# ---------------------------------------------------------------- unconditional requests

NOTES = (
    HEAD + '@app.post("/notes")\ndef create_note():\n    note = {"text": request.json["text"]}\n'
)


def test_positive_unconditional_status_needs_no_branch() -> None:
    before = NOTES + "    return jsonify(note)\n"
    after = NOTES + "    return jsonify(note), 201\n"
    assert run("Creating a note should return 201, not 200", before, after).status == (S.SATISFIED)


def test_negative_unconditional_status_not_returned() -> None:
    before = NOTES + "    return jsonify(note)\n"
    assert run("Creating a note should return 201, not 200", before, before).status == (
        S.NOT_SATISFIED
    )


# ---------------------------------------------------------------- error message content

BOOK = HEAD + '@app.get("/b/<int:book_id>")\ndef book(book_id):\n'


def test_positive_message_interpolates_the_value() -> None:
    before = BOOK + "    return jsonify(BOOKS[book_id])\n"
    after = BOOK + (
        "    if book_id not in BOOKS:\n"
        "        return jsonify({'error': f'no book {book_id}'}), 404\n"
        "    return jsonify(BOOKS[book_id])\n"
    )
    outcome = run("include the book id in the error message", before, after)
    assert outcome.status == S.SATISFIED


def test_adversarial_message_words_are_not_the_value() -> None:
    before = BOOK + "    return jsonify(BOOKS[book_id])\n"
    after = BOOK + (
        "    if book_id not in BOOKS:\n        return jsonify({'error': 'book id unknown'}), 404\n"
        "    return jsonify(BOOKS[book_id])\n"
    )
    outcome = run("include the book id in the error message", before, after)
    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["api.message_missing_value"] is False


# ---------------------------------------------------------------- return values

SEARCH = (
    "def search(index, q):\n    hits = index.lookup(q)\n    if not hits:\n        return None\n"
)


def test_positive_returns_new_value_instead_of_none() -> None:
    after = SEARCH.replace("return None", "return []") + "    return hits\n"
    outcome = run("Return an empty list instead of None", SEARCH + "    return hits\n", after, 2)
    assert outcome.status == S.SATISFIED


def test_negative_none_still_returned() -> None:
    before = SEARCH + "    return hits\n"
    outcome = run("Return an empty list instead of None", before, before, 2)
    assert outcome.status == S.NOT_SATISFIED
    assert kinds(outcome)["api.old_return_value"] is False
