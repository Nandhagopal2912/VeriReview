from helpers.cases import make_case
from verireview.contracts import CommitRef, ReviewCase
from verireview.evaluation.injection import INJECTIONS, Site, inject, no_change
from verireview.ingestion import make_unified_diff

BEFORE = "def save(db, username):\n    db.insert(username)\n"
AFTER = "def save(db, username):\n    check(username)\n    db.insert(username)\n"
TEXT = INJECTIONS[0]


def case() -> ReviewCase:
    base = make_case(BEFORE, AFTER, 2, tests={"t.py": "def test_a():\n    pass\n"})
    commit = CommitRef(sha="c1", message="fix", authored_at=None, committed_at=None)
    window = base.window.model_copy(update={"subsequent_commits": [commit]})
    diff = make_unified_diff(BEFORE, AFTER, "m.py", "m.py")
    return base.model_copy(update={"unified_diff": diff, "window": window})


def planted(site: Site) -> ReviewCase:
    variant = inject(case(), site, TEXT)
    assert variant is not None
    return variant


def test_code_sites_plant_a_comment_and_update_the_diff() -> None:
    eof = planted(Site.CODE_COMMENT_EOF)
    target = planted(Site.CODE_COMMENT_TARGET)

    assert eof.after_code is not None and eof.after_code.endswith(f"# {TEXT}\n")
    assert f"+# {TEXT}" in eof.unified_diff
    assert target.after_code is not None
    assert target.after_code.splitlines()[1] == f"    # {TEXT}"  # above line 2, same indent


def test_text_sites_carry_the_injection() -> None:
    assert planted(Site.REPLY).thread.comments[-1].body == TEXT
    assert planted(Site.COMMIT_MESSAGE).window.subsequent_commits[0].message.endswith(TEXT)
    assert planted(Site.PR_TITLE).pull_title.endswith(TEXT)
    assert planted(Site.TEST_COMMENT).test_files["t.py"].endswith(f"# {TEXT}\n")


def test_injection_only_is_the_unchanged_code_plus_a_comment() -> None:
    variant = planted(Site.INJECTION_ONLY)
    unchanged = no_change(case())

    assert unchanged is not None
    assert unchanged.after_code == BEFORE and unchanged.unified_diff == ""
    assert variant.after_code == f"def save(db, username):\n    # {TEXT}\n    db.insert(username)\n"
    assert variant.test_files == {}  # the test file was new: no change means it does not exist


def test_missing_sites_are_skipped() -> None:
    bare = make_case(None, None)

    assert inject(bare, Site.CODE_COMMENT_EOF, TEXT) is None
    assert inject(bare, Site.TEST_COMMENT, TEXT) is None
    assert inject(bare, Site.COMMIT_MESSAGE, TEXT) is None
    assert inject(bare, Site.INJECTION_ONLY, TEXT) is None


def test_comment_inside_a_multiline_string_falls_back_to_the_end() -> None:
    code = 'x = """\nline two\n"""\n'
    c = make_case(code, code, 2)

    variant = inject(c, Site.CODE_COMMENT_TARGET, TEXT)

    assert variant is not None and variant.after_code == code + f"# {TEXT}\n"
