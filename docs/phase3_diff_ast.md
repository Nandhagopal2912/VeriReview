# Phase 3: Diff and AST (Tree-sitter)

**Goal (roadmap):** identify the changed function/symbol and the structural changes relevant to
the review request.

## Components

| Module | Role |
|---|---|
| `diff/unified.py` | `unidiff` → typed `FileDiff` / `DiffHunk` / `DiffLine`; added/removed line sets |
| `diff/textual.py` | `difflib`: change regions, before→after **line mapping**, sequence similarity |
| `syntax/parser.py` | Tree-sitter parsing (pinned `tree-sitter~=0.26`, `tree-sitter-python~=0.25`). Never raises on bad code: `has_error` instead |
| `syntax/symbols.py` | Symbol index: functions / methods / classes, qualified names (`Class.method`, `outer.inner`), line ranges incl. decorators; innermost enclosing symbol |
| `syntax/facts.py` | Typed facts: `Call` (callee), `Condition` (kind, identifiers, `checks_none`, `checks_empty`), `Raise` (exception, bare?), `Handler` (exceptions, `swallows`, `reraises`), `Return` (value), identifiers |
| `syntax/structure.py` | Structural tokens that **ignore comments, docstrings and formatting**; position-independent fact diff (added/removed) |
| `syntax/location.py` | Code location resolution across revisions (plan §9) |
| `evidence/structure.py` | Evidence stage built on all of the above |

## Code location resolution (plan §9: "do not rely only on line numbers")

1. Enclosing symbol of the commented line in `before`: the **target**.
2. The same symbol in `after`: by **qualified name**, else (renamed) by the most **structurally
   similar new symbol** of the same kind (threshold 0.6), else `NOT_FOUND`.
3. Independently, follow the commented **line** via difflib's line mapping. If it now lives in a
   different symbol, the code **moved** (the plan's extracted-helper example), and that symbol is
   compared too.

Verified on: all 29 dev fixtures (100% correct target, including one rename), and 9 dedicated
scenarios: moved in file, renamed, extracted helper (plan §9), renamed method, added decorator,
nested function, module-level comment, deleted function, rename + rewrite below threshold.

## Structural evidence emitted

`target_symbol`, `target_after` (same / renamed + similarity / gone), `target_moved`,
`target_changed_structurally` (✓/✗, with "only comments, docstrings or formatting changed"),
one neutral item per **added/removed fact** (capped at 12), `other_symbols_changed` (unrelated
edits or upstream drift, the Phase 1 live finding L3), `file_changed_structurally`, and
`parse_error` when Tree-sitter saw syntax errors.

## Results on the dev set (same dataset hash `1754164a4b78…`)

| Pipeline | Accuracy | Macro-F1 | False acceptance | False blocking | Lexical traps caught |
|---|---|---|---|---|---|
| `phase2-locality-1` | 0.241 | 0.097 | 1.000 | 0.125 | 0 / 4 |
| `phase3-structure-1` | **0.310** | **0.165** | **0.889** | 0.125 | **2 / 4** |

Newly correct: `naming-003` (comment mentioning `discount_rate`) and `api-004` (TODO mentioning
`201 Created`). Both are recognised as "no code changed".

The Phase 3 aggregator is still "code changed ⇒ satisfied". It knows *that* the target changed,
not *whether the change does what was asked*. The evidence needed for that now exists. Example:
`validation-004` (asked for email validation) shows the only new code is
`logger.info("validating email address before sending")`, with no added condition. The Phase 5
rules turn such facts into verdicts.

Reports: `experiments/phase2_locality_baseline.json`, `experiments/phase3_structure.json`.

## Commands

```bash
uv run verireview verify-fixture dataset/fixtures/validation-004-docstring-only
uv run verireview eval-fixtures --pipeline phase2-locality   # compare with the baseline
uv run verireview eval-fixtures --out experiments/phase3_structure.json
```

## Known limitations

- Similarity-based rename matching can mis-pair two small, similar new functions. It is
  reported with its similarity score, so later stages can discount low scores.
- The line mapping cannot follow a commented line that was itself edited (`anchor_after_line`
  is then `None`). The symbol-level match still applies.
- Facts are syntactic (no data flow): "a None-check on `x` exists before the call" is checked
  by order of lines in Phase 5, not by control-flow analysis.
