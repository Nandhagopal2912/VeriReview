"""End-to-end ingestion through the real GitHubApi/GitHubClient, served by fixture data."""

import re

import pytest
from pydantic import SecretStr

from helpers.github import C2, C3, C4, FakeGitHub
from verireview.contracts import ReviewCase, WindowFlag
from verireview.gh.api import GitHubApi, RepoRef
from verireview.gh.client import GitHubClient
from verireview.gh.models import GhChangedFile
from verireview.ingestion import ingest_review_case, make_unified_diff
from verireview.ingestion.assemble import is_test_path

REPO = RepoRef("acme/shop")
TOKEN = SecretStr("t")


def ingest(token: SecretStr | None = TOKEN, comment_id: int = 5001) -> ReviewCase:
    client = GitHubClient(token, transport=FakeGitHub().transport, sleep=lambda _: None)
    return ingest_review_case(GitHubApi(client), REPO, 7, comment_id)


def test_reconstructs_thread_window_and_code() -> None:
    case = ingest()

    assert case.case_id == "acme/shop#7/5001"
    assert case.thread.is_resolved is True
    assert case.thread.resolved_by == "rev-bob"
    assert [c.id for c in case.thread.comments] == [5001, 5002, 5004]
    assert case.window.start_commit_sha == C2
    assert case.window.end_commit_sha == C4
    assert [c.sha for c in case.window.subsequent_commits] == [C3, C4]
    assert case.window.flags == [WindowFlag.RESOLUTION_TIME_UNKNOWN]


def test_before_after_and_diff_capture_the_change() -> None:
    case = ingest()

    assert case.before_code is not None and "if not username" not in case.before_code
    assert case.after_code is not None and "if not username" in case.after_code
    assert case.unified_diff.startswith("--- a/shop/user_service.py\n+++ b/shop/user_service.py\n")
    assert "+    if not username:\n" in case.unified_diff
    assert re.findall(r"^@@ .* @@$", case.unified_diff, flags=re.M) == ["@@ -1,2 +1,4 @@"]


def test_changed_test_files_are_collected() -> None:
    case = ingest()

    assert [f.path for f in case.changed_files if f.is_test] == ["tests/test_user_service.py"]
    assert "def test_empty_username_rejected" in case.test_files["tests/test_user_service.py"]


def test_any_comment_in_thread_selects_the_thread() -> None:
    assert ingest(comment_id=5004).thread.root_comment_id == 5001


def test_without_token_resolution_is_unknown_but_ingestion_works() -> None:
    case = ingest(token=None)

    assert case.thread.is_resolved is None
    assert WindowFlag.RESOLUTION_STATE_UNKNOWN in case.window.flags
    assert case.after_code is not None


def test_case_round_trips_through_json() -> None:
    case = ingest()

    assert ReviewCase.model_validate_json(case.model_dump_json()) == case


class _Reader(GitHubApi):
    """Fixture reader with overridable file/compare behaviour for edge cases."""

    def __init__(
        self,
        compare: list[GhChangedFile] | None = None,
        override_compare: bool = False,
        files: dict[tuple[str, str], str | None] | None = None,
    ) -> None:
        super().__init__(GitHubClient(SecretStr("t"), transport=FakeGitHub().transport))
        self._compare = compare
        self._override_compare = override_compare
        self._files = files or {}

    def compare_files(self, repo: RepoRef, base: str, head: str) -> list[GhChangedFile] | None:
        if self._override_compare:
            return self._compare
        return super().compare_files(repo, base, head)

    def get_file(self, repo: RepoRef, path: str, ref: str) -> str | None:
        if (path, ref) in self._files:
            return self._files[(path, ref)]
        return super().get_file(repo, path, ref)


def test_renamed_file_is_followed() -> None:
    renamed = [
        GhChangedFile(
            filename="shop/users.py", status="renamed", previous_filename="shop/user_service.py"
        )
    ]
    reader = _Reader(
        compare=renamed,
        override_compare=True,
        files={("shop/users.py", C4): "def save_user(): ...\n"},
    )

    case = ingest_review_case(reader, REPO, 7, 5001)

    assert case.file_path == "shop/users.py"
    assert WindowFlag.FILE_RENAMED in case.window.flags
    assert case.unified_diff.startswith("--- a/shop/user_service.py\n+++ b/shop/users.py\n")


def test_deleted_file_is_flagged() -> None:
    reader = _Reader(files={("shop/user_service.py", C4): None})

    case = ingest_review_case(reader, REPO, 7, 5001)

    assert case.after_code is None
    assert WindowFlag.FILE_DELETED in case.window.flags
    assert "+++ /dev/null" in case.unified_diff


def test_unreachable_start_commit_uses_whole_pr_files() -> None:
    reader = _Reader(
        compare=None, override_compare=True, files={("shop/user_service.py", C2): None}
    )

    case = ingest_review_case(reader, REPO, 7, 5001)

    assert case.before_code is None
    assert {WindowFlag.BEFORE_CODE_UNAVAILABLE, WindowFlag.CHANGED_FILES_FROM_WHOLE_PR} <= set(
        case.window.flags
    )


def test_crlf_is_normalised() -> None:
    reader = _Reader(files={("shop/user_service.py", C2): "a\r\nb\r\n"})

    case = ingest_review_case(reader, REPO, 7, 5001)

    assert case.before_code == "a\nb\n"


def test_diff_marks_missing_final_newline() -> None:
    diff = make_unified_diff("x = 1", "x = 2", "a.py", "a.py")

    assert diff.endswith("+x = 2\n\\ No newline at end of file\n")


def test_diff_of_identical_code_is_empty() -> None:
    assert make_unified_diff("x\n", "x\n", "a.py", "a.py") == ""


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("tests/test_api.py", True),
        ("pkg/tests/helpers.py", True),
        ("test_x.py", True),
        ("pkg/x_test.py", True),
        ("conftest.py", True),
        ("pkg/testing.py", False),
        ("pkg/contest.py", False),
        ("tests/data.json", False),
    ],
)
def test_is_test_path(path: str, expected: bool) -> None:
    assert is_test_path(path) is expected
