"""Comment text handling: clean-up, masking, sentence and clause splitting.

Inline code (`` `x` ``) and parentheticals are *masked* before splitting so boundaries never fall
inside them: `` `.json()` `` must not end a sentence, "(non-empty, max 32 chars)" must not become
two clauses. Masks are restored in every returned string.
"""

import re
from dataclasses import dataclass, field

from verireview.requirements.lexicon import ACTION_VERBS, CONTRAST_STARTS, LEADING_FILLERS

_SUGGESTION = re.compile(r"```suggestion[^\n]*\n(.*?)```", re.S)
_CODE_BLOCK = re.compile(r"```.*?```", re.S)
_HTML_TAG = re.compile(r"<[^>]+>")
_MD_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_URL = re.compile(r"https?://\S+")
_INLINE_CODE = re.compile(r"`[^`\n]+`")
_PAREN = re.compile(r"\([^()\n]*\)")
_ABBREVIATIONS = re.compile(r"\b(e\.g\.|i\.e\.|etc\.|vs\.)", re.I)
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+", re.M)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_CLAUSE_DELIMITER = re.compile(
    r"(\s*;\s*|\s*:\s+|\s+[-–—]\s+|\s*,\s*|\s+(?:and|then|otherwise)\s+)", re.I
)
_POLITE_PREFIX = re.compile(
    r"^(?:(?:could|can|would|will)\s+(?:you|we|u)\s+(?:please\s+)?|please\s+)", re.I
)
_NEGATED_VERB = re.compile(r"^(?:don'?t|do not|never)\s+(\S+)", re.I)


@dataclass(frozen=True)
class Prepared:
    text: str  # cleaned comment, code blocks removed
    suggestions: tuple[str, ...]  # contents of ```suggestion blocks


@dataclass
class Masked:
    """Text with inline code and parentheticals replaced by placeholders."""

    text: str
    spans: list[str] = field(default_factory=list)

    def restore(self, text: str) -> str:
        for index, original in reversed(list(enumerate(self.spans))):
            text = text.replace(_placeholder(index), original)
        return text


def prepare(comment: str) -> Prepared:
    suggestions = tuple(s.rstrip("\n") for s in _SUGGESTION.findall(comment))
    text = _SUGGESTION.sub(" ", comment)
    text = _CODE_BLOCK.sub(" ", text)
    text = _MD_LINK.sub(r"\1", text)
    text = _HTML_TAG.sub(" ", text)
    text = _URL.sub(" ", text)
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith(">")]  # quotes
    text = _BULLET.sub("", "\n".join(lines))
    return Prepared(text=text.strip(), suggestions=suggestions)


def mask(text: str) -> Masked:
    masked = Masked(text)
    for pattern in (_INLINE_CODE, _ABBREVIATIONS, _PAREN):
        masked.text = pattern.sub(lambda m: _store(masked, m.group(0)), masked.text)
    return masked


def split_sentences(masked: Masked) -> list[str]:
    """Masked sentences: split on line breaks and sentence-final punctuation."""
    sentences: list[str] = []
    for line in masked.text.splitlines():
        sentences += [s.strip() for s in _SENTENCE_END.split(line) if s.strip()]
    return sentences


def split_clauses(sentence: str) -> list[str]:
    """Split a masked sentence into clauses, each starting with its own request verb.

    A delimiter (``,`` ``;`` ``:`` `` - `` ``and`` ``then`` ``otherwise``) only starts a new
    clause when what follows begins with an action verb; otherwise it is part of the current
    clause ("between 0 and 150", "…, we have no trace of these").
    """
    parts = _CLAUSE_DELIMITER.split(sentence)
    clauses: list[str] = []
    current = parts[0]
    for delimiter, segment in zip(parts[1::2], parts[2::2], strict=True):
        if starts_with_request(segment) and not _is_contrast(segment):
            clauses.append(current)
            current = segment
        else:
            current += delimiter + segment
    clauses.append(current)
    return [c.strip() for c in clauses if c.strip()]


def leading_verb(clause: str) -> str | None:
    """The request verb a clause starts with, after fillers and polite prefixes, if any."""
    words = _strip_prefixes(clause).split()
    if not words:
        return None
    if words[0].lower() == "consider" and len(words) > 1:
        # "Consider renaming …" is a hedged request for "rename".
        return _gerund_stem(words[1].lower().strip(",.;:!?"))
    negated = _NEGATED_VERB.match(" ".join(words))
    word = (negated.group(1) if negated else words[0]).lower().strip(",.;:!?")
    return word if word in ACTION_VERBS else None


def _gerund_stem(word: str) -> str | None:
    """Verb stem of a gerund (renaming → rename, splitting → split); None if not a verb."""
    if not word.endswith("ing"):
        return None
    stem = word[:-3]
    for candidate in (stem, stem + "e", stem[:-1]):
        if candidate in ACTION_VERBS:
            return candidate
    return None


def starts_with_request(clause: str) -> bool:
    return leading_verb(clause) is not None


def strip_fillers(clause: str) -> str:
    return _strip_prefixes(clause).rstrip(" .;:!?,")


def _strip_prefixes(clause: str) -> str:
    text = clause.strip()
    changed = True
    while changed:
        changed = False
        polite = _POLITE_PREFIX.match(text)
        if polite:
            text, changed = text[polite.end() :], True
        first, _, rest = text.partition(" ")
        if first.lower().strip(",") in LEADING_FILLERS and rest:
            text, changed = rest, True
    return text


def _is_contrast(segment: str) -> bool:
    return segment.strip().lower().startswith(CONTRAST_STARTS)


def _store(masked: Masked, original: str) -> str:
    masked.spans.append(original)
    return _placeholder(len(masked.spans) - 1)


def _placeholder(index: int) -> str:
    return f"\x00{index}\x00"
