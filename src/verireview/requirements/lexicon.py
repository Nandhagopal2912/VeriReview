"""Word lists and patterns for rule-based requirement extraction.

Kept in one place so the extractor's behaviour is inspectable and every change is reviewable.
All matching is case-insensitive unless noted.
"""

import re

# Imperative verbs that start a requested change. A clause starting with one is a request.
ACTION_VERBS = frozenset(
    [
        "abort",
        "add",
        "adjust",
        "allow",
        "assert",
        "avoid",
        "call",
        "cache",
        "catch",
        "change",
        "check",
        "clean",
        "convert",
        "cover",
        "create",
        "delete",
        "document",
        "drop",
        "ensure",
        "extract",
        "fall",
        "fix",
        "give",
        "guard",
        "handle",
        "ignore",
        "include",
        "keep",
        "log",
        "make",
        "mention",
        "move",
        "normalize",
        "normalise",
        "pass",
        "raise",
        "re-raise",
        "reraise",
        "reject",
        "remove",
        "reply",
        "respond",
        "rename",
        "replace",
        "retry",
        "return",
        "reuse",
        "set",
        "simplify",
        "split",
        "store",
        "swallow",
        "test",
        "throw",
        "update",
        "use",
        "validate",
        "verify",
        "wrap",
        "write",
    ]
)

# Words that may precede the verb without changing it ("please add", "and then add").
LEADING_FILLERS = frozenset(
    [
        "please",
        "and",
        "then",
        "also",
        "so",
        "otherwise",
        "just",
        "maybe",
        "kindly",
        "additionally",
        "finally",
        "but",
        "or",
    ]
)

# A clause starting with these contrasts with the previous one ("…, not return None").
CONTRAST_STARTS = ("not ", "instead of", "rather than", "instead,", "e.g.", "i.e.", "like ")

HEDGES = re.compile(
    r"\b(maybe|perhaps|probably|possibly|might|consider|considering|i think|i guess|"
    r"not sure|hmm+|could be|would be nice|optional(ly)?)\b",
    re.IGNORECASE,
)

# Questions phrased as polite requests are requests, not uncertainty.
POLITE_REQUEST = re.compile(
    r"^\s*(could|can|would|will)\s+(you|we|u)\b|^\s*(please|pls)\b", re.IGNORECASE
)
# Questions that imply a change even without an imperative verb.
IMPLIED_REQUEST_QUESTION = re.compile(r"\b(what happens (if|when)|what if|why not)\b", re.I)

CHIT_CHAT = re.compile(
    r"^\s*(lgtm|thanks|thank you|thx|nice|great|looks good|good point|done|ok(ay)?|cool|"
    r"good catch|agreed|\+1|👍)\b",
    re.IGNORECASE,
)

# "`a` -> `b`" / "`a` → `b`": a rename written as an arrow (common in "nit:" comments).
RENAME_ARROW = re.compile(r"`([A-Za-z_]\w*)`\s*(?:->|→|=>)\s*`([A-Za-z_]\w*)`")
RENAME_PAIR = re.compile(r"`([A-Za-z_][\w.]*)`\s+(?:to|->|→|=>)\s+`([A-Za-z_][\w.]*)`", re.I)

# ---------------------------------------------------------------- category cues

TESTING = re.compile(
    r"\b(unit |integration )?tests?\b|\btesting\b|\bcoverage\b|\btest case|\bcover(s|ed)?\b", re.I
)
NAMING = re.compile(
    r"\brenam\w*|\bnames?\b|\bnaming\b|\bcalled\b|\bdescriptive\b|snake_case|camelcase|"
    r"\bcall (?:it|this|that|them)\b",
    re.I,
)
# "Something like `normalized_email` would be better": a new name offered as an example.
SOFT_RENAME = re.compile(r"\bsomething like\s+`[A-Za-z_]\w*`", re.I)
# "Return an empty list instead of None": what an interface returns (API behaviour, not a check).
RETURN_VALUE = re.compile(
    r"\breturn\w*\s+(?:an?\s+)?(?:empty\s+\w+|\[\]|\{\}|None|False|True|0|`[^`]+`)\s+"
    r"(?:instead\s+of|rather\s+than)\b",
    re.I,
)
# Documentation requests ("add a docstring explaining …") are `other`, whatever else they mention.
DOCS = re.compile(r"\bdocstrings?\b|\bdocument(?:ation|ed)?\b|\bcomments?\b|\btype hints?\b", re.I)
DOCS_VERBS = frozenset({"add", "write", "document", "update", "include", "mention", "fix"})
API = re.compile(
    r"\bhttp\b|\bstatus( code)?\b|\bendpoint\b|\bheaders?\b|\bidempoten\w*|"
    r"\b(200|201|202|204|301|302|304|400|401|403|404|405|409|410|415|422|429|500|502|503|504)\b"
    r"(?!\s*%)|\bcreated\b|\bnot found\b|\bbad request\b|\bresponse code\b",
    re.I,
)
# Prefix is optional so a bare `Timeout` (e.g. `requests.Timeout`) matches too.
EXCEPTION_NAME = re.compile(r"\b((?:[A-Z]\w*?)?(?:Error|Exception|Timeout|NotFound))\b")
ERROR_HANDLING = re.compile(
    r"\b(handle[sd]?|catch|except|try/except|retry|re-?rais\w*|fall(s)? back|fallback|crash\w*|"
    r"fails?|failure|stack ?trace|traceback|swallow\w*|what happens (if|when)|malformed|"
    r"exceptions?|error handling|log(s|ged|ging)?|ignor(e|es|ed|ing)|suppress\w*|"
    r"clos(e|ed|es)|releas(e|ed|es)|even if|clean(ed)? ?up|finally)\b",
    re.I,
)
VALIDATION = re.compile(
    r"\b(validat\w*|check|null|none|empty|non-empty|blank|positive|negative|between|range|"
    r"format|must be|is (?:\w+ )?an? (int|str|string|integer|number)|guard|sanitiz\w*|required|"
    r"missing|valid|reject\w*|"
    r"return early|early return|bail out|guard clause)\b",
    re.I,
)
# Raising these signals rejection of invalid input: a validation outcome, not error handling.
VALIDATION_EXCEPTIONS = frozenset({"ValueError", "TypeError"})

# ---------------------------------------------------------------- ambiguity

VAGUE = re.compile(
    r"\b(better|cleaner|nicer|clearer|something|somehow|more specific|improve\w*|smaller)\b",
    re.I,
)
UNVERIFIABLE = re.compile(
    r"\b(idempoten\w*|thread[- ]safe|performant|faster|scal(e|able)|secure|robust|cache|"
    r"refactor\w*|split|simplif\w*|clean ?up|restructur\w*|tidy)\b",
    re.I,
)

# Ambiguity weights (sum clamped to 1.0). A case is UNCERTAIN at or above the threshold.
# A genuine (non-polite) question alone reaches the threshold: the reviewer asked, not
# requested, so what would satisfy them is undetermined (dev fixture errors-005).
WEIGHT_QUESTION = 0.5
WEIGHT_HEDGE = 0.35
WEIGHT_NO_TARGET = 0.2
WEIGHT_VAGUE = 0.15
WEIGHT_UNVERIFIABLE = 0.2
AMBIGUITY_THRESHOLD = 0.5

# Predicates that can follow "and" in "`x` is P1 and P2" (validation conjunctions).
PREDICATE_HEADS = re.compile(
    r"^(between|non-|not |an? |positive|negative|greater|less|at (most|least)|within|in |"
    r"one of|valid|shorter|longer|lower|upper)",
    re.I,
)

# "docstring please." / "Type hints please": a short noun phrase + please is a request.
NOUN_PLEASE = re.compile(r"^\s*(?:[\w`'-]+\s+){0,3}[\w`'-]+,?\s+please\s*[.!]?\s*$", re.I)
