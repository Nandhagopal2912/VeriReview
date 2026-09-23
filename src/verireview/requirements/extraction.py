"""Rule-based requirement extraction (Phase 4, step B).

comment ─► clean-up ─► sentences ─► utterance type ─► clauses ─► expansion ─► category + target
                                                                                ─► ambiguity

Every step is a small deterministic rule so its behaviour can be read, tested and measured.
Scores against gold annotations: ``verireview eval-requirements``.
"""

import difflib
import re
from dataclasses import dataclass

from verireview.contracts import (
    Requirement,
    RequirementCategory,
    ReviewCase,
    ReviewRequirement,
    Utterance,
    UtteranceType,
)
from verireview.requirements import lexicon as lx
from verireview.requirements.text import (
    Masked,
    leading_verb,
    mask,
    prepare,
    split_clauses,
    split_sentences,
    strip_fillers,
)
from verireview.syntax import enclosing_symbol, extract_facts, index_symbols, parse

Category = RequirementCategory

_MODAL = re.compile(r"\b(should|must|needs? to|has to|have to|ought to)\b", re.I)
# Modal plus the next few words: "should probably cache" has its verb two words later.
_MODAL_VERB = re.compile(
    r"\b(?:should|must|needs? to|has to|have to|ought to)\s+((?:[\w-]+\s+){0,2}[\w-]+)", re.I
)
_OBJECT_END = re.compile(r"\s(?:is|are|before|after|when|if|so|since|because|otherwise)\s", re.I)
_COORDINATION = re.compile(r"\s(?:and|or)\s|,")
_CONDITION_START = re.compile(r"^\s*(if|when|whenever|where|unless|in case)\b", re.I)
_IN_CLAUSE_CONDITION = re.compile(r"\b(when|if|whenever|unless|in case)\b\s+(.+)$", re.I)
_BACKTICK_IDENT = re.compile(r"`\.?([A-Za-z_][\w.]*)(?:\([^`]*\))?`")
_WORD = re.compile(r"[A-Za-z_]\w*")
# Only the verb is case-insensitive: with re.I, [A-Z] would also match "raise *it*".
_RAISED = re.compile(r"\b(?i:raise|throw)s?\s+(?:an?\s+)?`?([A-Z]\w*)")
_TEST_OBJECTS = re.compile(r"\btests?\b.*?\bfor\s+(?:both\s+)?(.+)$", re.I)
_TEST_ITEM_SPLIT = re.compile(
    r"\s*,\s*(?:and\s+)?|\s+(?:and|or)\s+(?:one\s+)?(?:for\s+)?(?:the\s+)?", re.I
)
_VALIDATE_VERBS = frozenset({"validate", "check", "verify", "guard"})
_CODE_TOKEN = re.compile(r"[A-Za-z_]\w*|\S")
_CONSTANTS = frozenset({"None", "True", "False"})


@dataclass(frozen=True)
class CodeContext:
    """What the extractor may know about the commented code (all optional)."""

    identifiers: frozenset[str] = frozenset()
    lines: tuple[str, ...] = ()
    target_symbol: str | None = None

    @classmethod
    def from_code(cls, code: str | None, anchor_line: int | None = None) -> "CodeContext":
        if not code:
            return cls()
        tree = parse(code)
        symbol = (
            enclosing_symbol(index_symbols(tree), anchor_line) if anchor_line is not None else None
        )
        return cls(
            identifiers=extract_facts(tree.root_node).identifiers,
            lines=tuple(code.split("\n")),
            target_symbol=symbol.qualified_name if symbol else None,
        )


@dataclass(frozen=True)
class _Draft:
    description: str
    category: Category
    target_hint: str | None = None
    condition: str | None = None
    suggested_code: str | None = None


# ---------------------------------------------------------------- public API


def extract_requirements(
    comment: str,
    *,
    case_id: str = "adhoc",
    target_file: str = "",
    context: CodeContext | None = None,
) -> ReviewRequirement:
    ctx = context or CodeContext()
    prepared = prepare(comment)
    masked = mask(prepared.text)

    utterances: list[Utterance] = []
    drafts: list[_Draft] = []
    for sentence in split_sentences(masked):
        utterance = classify_sentence(sentence, masked)
        utterances.append(utterance)
        if utterance.actionable:
            drafts += _sentence_drafts(sentence, masked)
    drafts += [_suggestion_draft(block, ctx) for block in prepared.suggestions]

    if not drafts:
        return ReviewRequirement(
            case_id=case_id,
            target_file=target_file,
            target_symbol=ctx.target_symbol,
            requirements=[
                Requirement(id="R1", category=Category.OTHER, description=comment.strip()[:300])
            ],
            actionable=False,
            ambiguity=1.0,
            ambiguity_reasons=["the comment contains no actionable request"],
            utterances=utterances,
            source="extracted",
        )

    requirements = [
        _to_requirement(f"R{i}", draft, ctx, prepared.text)
        for i, draft in enumerate(drafts, start=1)
    ]
    score, reasons = ambiguity(utterances, requirements, masked)
    return ReviewRequirement(
        case_id=case_id,
        target_file=target_file,
        target_symbol=ctx.target_symbol,
        requirements=requirements,
        actionable=True,
        ambiguity=score,
        ambiguity_reasons=reasons,
        utterances=utterances,
        source="extracted",
    )


def extraction_stage(case: ReviewCase) -> ReviewRequirement:
    """Pipeline requirement stage: extract from the thread's root comment + commented code."""
    return extract_requirements(
        case.thread.root.body,
        case_id=case.case_id,
        target_file=case.file_path,
        context=CodeContext.from_code(case.before_code, case.anchor_line),
    )


# ---------------------------------------------------------------- sentences


def classify_sentence(sentence: str, masked: Masked) -> Utterance:
    """Utterance type and whether the sentence asks for a change (plan §7)."""
    text = masked.restore(sentence)
    clauses = split_clauses(sentence)
    has_request = any(leading_verb(c) for c in clauses)
    arrow = lx.RENAME_ARROW.search(text) is not None
    modal_verb = any(
        word.lower() in lx.ACTION_VERBS
        for m in _MODAL_VERB.finditer(sentence)
        for word in m.group(1).split()
    )
    modal_cue = _MODAL.search(sentence) is not None and categorize(text, None) is not None
    hedged = lx.HEDGES.search(sentence) is not None

    if lx.CHIT_CHAT.match(text) and not (has_request or arrow):
        return Utterance(text=text, type=UtteranceType.CHIT_CHAT, actionable=False)
    if text.rstrip().endswith("?"):
        polite = lx.POLITE_REQUEST.search(text) is not None
        actionable = (
            has_request
            or arrow
            or modal_verb
            or lx.IMPLIED_REQUEST_QUESTION.search(text) is not None
            or categorize(text, None) is not None
        )
        kind = UtteranceType.REQUIREMENT if polite and has_request else UtteranceType.QUESTION
        return Utterance(text=text, type=kind, actionable=actionable)
    if has_request or arrow or modal_verb or modal_cue:
        kind = UtteranceType.SUGGESTION if hedged else UtteranceType.REQUIREMENT
        return Utterance(text=text, type=kind, actionable=True)
    return Utterance(text=text, type=UtteranceType.EXPLANATION, actionable=False)


def _sentence_drafts(sentence: str, masked: Masked) -> list[_Draft]:
    """Requirements in one actionable sentence: one per request clause, then expanded."""
    clauses = split_clauses(sentence)
    if not any(leading_verb(c) for c in clauses):
        clauses = [sentence]  # actionable via modal / question / arrow: the whole sentence
        whole = True
    else:
        whole = False

    drafts: list[_Draft] = []
    pending_condition: str | None = None
    previous: Category | None = None
    for clause in clauses:
        verb = leading_verb(clause)
        if verb is None and not whole:
            # Not a request: a leading "if/when…" clause is the condition of the next request.
            if _CONDITION_START.match(clause):
                pending_condition = masked.restore(clause)
            continue
        text = masked.restore(clause)
        condition = pending_condition or _in_clause_condition(text)
        # Only a *separate* condition clause adds text; an in-clause one is already in `text`
        # (counting it twice skewed categories: live in api-003 and held-out h18).
        cue_text = f"{pending_condition} {text}" if pending_condition else text
        pending_condition = None
        category = categorize(cue_text, verb) or previous or Category.OTHER
        previous = category
        drafts += _expand(text, category, verb, condition)
    return drafts


# ---------------------------------------------------------------- categories


def categorize(text: str, verb: str | None) -> Category | None:
    """Category from lexical cues; None when nothing points anywhere.

    Testing and naming cues are decisive. Otherwise API, error-handling and validation cues are
    counted; ties go to the more specific category (API > error handling > validation).
    Raising ValueError/TypeError is rejection of invalid input, i.e. validation.
    """
    if lx.TESTING.search(text) or verb == "test":
        return Category.TESTING
    if verb == "rename" or lx.RENAME_ARROW.search(text) or lx.NAMING.search(_unquote(text)):
        return Category.NAMING

    raised = {m.group(1) for m in _RAISED.finditer(text)}
    exceptions = set(lx.EXCEPTION_NAME.findall(text))
    handled = exceptions - (raised & lx.VALIDATION_EXCEPTIONS)
    scores = {
        Category.API_BEHAVIOR: len(lx.API.findall(text)),
        Category.ERROR_HANDLING: len(lx.ERROR_HANDLING.findall(text)) + len(handled),
        Category.VALIDATION: len(lx.VALIDATION.findall(text))
        + 2 * len(raised & lx.VALIDATION_EXCEPTIONS),
    }
    best = max(scores.values())
    if best == 0:
        return None
    for category in (Category.API_BEHAVIOR, Category.ERROR_HANDLING, Category.VALIDATION):
        if scores[category] == best:
            return category
    return None  # unreachable


def _unquote(text: str) -> str:
    """Text without inline code, so identifiers like `display_name` don't look like naming cues."""
    return re.sub(r"`[^`]*`", " ", text)


# ---------------------------------------------------------------- expansion


def _expand(text: str, category: Category, verb: str | None, condition: str | None) -> list[_Draft]:
    """Split coordinated objects into separate requirements (plan §7: one per requirement)."""
    base = strip_fillers(text)

    if category == Category.NAMING:
        pairs = lx.RENAME_ARROW.findall(text) or lx.RENAME_PAIR.findall(text)
        if len(pairs) >= 2:
            return [_Draft(f"Rename `{a}` to `{b}`", category, a, condition) for a, b in pairs]
        if pairs:
            return [_Draft(base, category, pairs[0][0], condition)]

    if category == Category.TESTING:
        match = _TEST_OBJECTS.search(base)
        if match:
            items = [i.strip(" .") for i in _TEST_ITEM_SPLIT.split(match.group(1)) if i.strip(" .")]
            if len(items) >= 2:
                return [
                    _Draft(f"Add a test for {item}", category, None, condition) for item in items
                ]

    if category == Category.ERROR_HANDLING:
        raised = {m.group(1) for m in _RAISED.finditer(text)}
        names = [
            n
            for n in dict.fromkeys(lx.EXCEPTION_NAME.findall(f"{condition or ''} {text}"))
            if n not in raised
        ]
        if len(names) >= 2:
            return [_Draft(f"{base} (for `{n}`)", category, n, condition) for n in names]

    if category == Category.VALIDATION:
        # Several subjects only when they are coordinated in the verb's object ("A and B"),
        # not when a second identifier appears later ("before calling `.json()`").
        object_part = _OBJECT_END.split(text, maxsplit=1)[0]
        subjects = _BACKTICK_IDENT.findall(object_part)
        if verb in _VALIDATE_VERBS and len(subjects) >= 2 and _COORDINATION.search(object_part):
            return [_Draft(f"Validate `{s}`", category, s, condition) for s in subjects]
        predicates = _predicate_conjunction(text)
        if predicates:
            subject, parts = predicates
            return [
                _Draft(f"Validate that {subject} is {p}", category, None, condition) for p in parts
            ]

    return [_Draft(base, category, None, condition)]


def _predicate_conjunction(text: str) -> tuple[str, list[str]] | None:
    """ "`age` is an int and between 0 and 150" → ("`age`", ["an int", "between 0 and 150"])."""
    head, sep, tail = text.partition(" is ")
    if not sep:
        return None
    parts: list[str] = []
    for piece in re.split(r"\s+and\s+", tail.rstrip(" .")):
        if parts and not lx.PREDICATE_HEADS.match(piece):
            parts[-1] += f" and {piece}"
        else:
            parts.append(piece)
    if len(parts) < 2:
        return None
    subject = head.split()[-1] if head.split() else head
    return subject, parts


def _in_clause_condition(text: str) -> str | None:
    match = _IN_CLAUSE_CONDITION.search(text)
    return match.group(2).rstrip(" .") if match else None


def _suggestion_draft(block: str, ctx: CodeContext) -> _Draft:
    """A GitHub suggestion is the exact expected code; compare it to the closest code line."""
    first = next((ln for ln in block.split("\n") if ln.strip()), "")
    category, target = Category.OTHER, None
    if first and ctx.lines:
        closest = max(
            ctx.lines,
            key=lambda ln: difflib.SequenceMatcher(None, ln.strip(), first.strip()).ratio(),
        )
        old, new = _CODE_TOKEN.findall(closest), _CODE_TOKEN.findall(first)
        changed = [(a, b) for a, b in zip(old, new, strict=False) if a != b]
        if (
            len(old) == len(new)
            and changed
            and all(_WORD.fullmatch(a) and _WORD.fullmatch(b) for a, b in changed)
        ):
            category, target = Category.NAMING, changed[0][0]
    return _Draft(
        f"Apply the suggested change: `{first.strip()}`",
        category,
        target,
        suggested_code=block,
    )


# ---------------------------------------------------------------- requirement objects


def _to_requirement(rid: str, draft: _Draft, ctx: CodeContext, comment: str) -> Requirement:
    expected = draft.description
    if draft.condition and draft.condition in expected:
        expected = expected.replace(draft.condition, "").rstrip(" ,.")
        expected = re.sub(r"\s+\b(when|if|whenever|unless|in case)$", "", expected, flags=re.I)
    return Requirement(
        id=rid,
        category=draft.category,
        description=draft.description,
        target=draft.target_hint
        or _find_target(draft.description, ctx)
        or _find_target(comment, ctx),
        condition=draft.condition,
        expected_behavior=expected or None,
        suggested_code=draft.suggested_code,
    )


def _find_target(text: str, ctx: CodeContext) -> str | None:
    """Backticked identifiers first (preferring ones in the code), then plain words in the code."""
    quoted: list[str] = [q for q in _BACKTICK_IDENT.findall(text) if q not in _CONSTANTS]
    if quoted:
        in_code = [q for q in quoted if q.split(".")[0] in ctx.identifiers]
        return (in_code or quoted)[0]
    if not ctx.identifiers:
        return None
    words = [w.lower() for w in _WORD.findall(_unquote(text))]
    candidates = words + [f"{a}_{b}" for a, b in zip(words, words[1:], strict=False)]
    return next((c for c in candidates if c in ctx.identifiers), None)


# ---------------------------------------------------------------- ambiguity


def ambiguity(
    utterances: list[Utterance], requirements: list[Requirement], masked: Masked
) -> tuple[float, list[str]]:
    """Heuristic ambiguity in [0, 1] with human-readable reasons (plan §8: `ambiguity`).

    Not a probability: an additive score over explicit signals. Threshold in the lexicon.
    """
    actionable = [u for u in utterances if u.actionable]
    text = " ".join(u.text for u in actionable)
    plain = _unquote(text)
    signals = [
        (
            any(u.type == UtteranceType.QUESTION for u in actionable),
            lx.WEIGHT_QUESTION,
            "phrased as a question, not a request",
        ),
        (lx.HEDGES.search(plain) is not None, lx.WEIGHT_HEDGE, "hedged ('maybe', 'probably', …)"),
        (
            all(r.target is None for r in requirements),
            lx.WEIGHT_NO_TARGET,
            "no identifiable code target",
        ),
        (lx.VAGUE.search(plain) is not None, lx.WEIGHT_VAGUE, "vague wording"),
        (
            lx.UNVERIFIABLE.search(plain) is not None,
            lx.WEIGHT_UNVERIFIABLE,
            "asks for a property that is hard to verify statically",
        ),
    ]
    score = min(1.0, sum(weight for present, weight, _ in signals if present))
    return round(score, 2), [reason for present, _, reason in signals if present]
