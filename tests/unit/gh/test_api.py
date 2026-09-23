import json

import httpx2 as httpx
import pytest
from pydantic import SecretStr

from helpers.github import C2, C4, FakeGitHub
from verireview.gh.api import GitHubApi, RepoRef
from verireview.gh.client import GitHubClient

REPO = RepoRef("acme/shop")
TOKEN = SecretStr("t")


def make_api(fake: FakeGitHub, token: SecretStr | None = TOKEN) -> GitHubApi:
    return GitHubApi(GitHubClient(token, transport=fake.transport, sleep=lambda _: None))


@pytest.mark.parametrize("value", ["acme", "acme/shop/extra", "../x/y", "a b/c", "acme/", "/shop"])
def test_repo_ref_rejects_invalid_names(value: str) -> None:
    with pytest.raises(ValueError):
        RepoRef(value)


def test_repo_ref_accepts_owner_and_name() -> None:
    ref = RepoRef("pallets/click.py-3")

    assert (ref.owner, ref.name, str(ref)) == ("pallets", "click.py-3", "pallets/click.py-3")


def test_parses_pull_request() -> None:
    pull = make_api(FakeGitHub()).get_pull(REPO, 7)

    assert (pull.number, pull.title, pull.head.sha) == (7, "Add user service", C4)


def test_commit_author_email_is_not_modelled() -> None:
    commits = make_api(FakeGitHub()).list_pull_commits(REPO, 7)

    assert len(commits) == 4
    assert "email" not in commits[0].commit.model_dump_json()


def test_thread_states_from_graphql() -> None:
    states = make_api(FakeGitHub()).list_thread_states(REPO, 7)

    by_root = {s.root_comment_id: s for s in states}
    assert by_root[5001].is_resolved is True
    assert by_root[5001].resolved_by == "rev-bob"
    assert by_root[5003].is_resolved is False


def test_cannot_read_thread_state_without_token() -> None:
    assert make_api(FakeGitHub(), token=None).can_read_thread_state is False


def test_get_file_returns_none_when_missing() -> None:
    assert make_api(FakeGitHub()).get_file(REPO, "shop/nope.py", C2) is None


def test_get_file_quotes_path_and_passes_ref() -> None:
    fake = FakeGitHub()
    make_api(fake).get_file(REPO, "dir with space/a#b.py", C2)

    request = fake.requests[-1]
    assert request.url.raw_path.startswith(b"/repos/acme/shop/contents/dir%20with%20space/a%23b.py")
    assert request.url.params["ref"] == C2


def test_get_file_rejects_non_sha_ref() -> None:
    with pytest.raises(ValueError, match="Not a commit SHA"):
        make_api(FakeGitHub()).get_file(REPO, "a.py", "main; rm -rf")


def test_compare_returns_none_for_unreachable_commit() -> None:
    assert make_api(FakeGitHub()).compare_files(REPO, "9" * 40, C4) is None


def test_compare_lists_changed_files() -> None:
    files = make_api(FakeGitHub()).compare_files(REPO, C2, C4)

    assert files is not None
    assert [f.filename for f in files] == ["shop/user_service.py", "tests/test_user_service.py"]


def test_thread_states_follow_graphql_pagination() -> None:
    pages = iter(
        [
            {"hasNextPage": True, "endCursor": "abc", "id": "1"},
            {"hasNextPage": False, "endCursor": None, "id": "2"},
        ]
    )
    cursors: list[object] = []

    def handler(request: httpx.Request) -> httpx.Response:
        cursors.append(json.loads(request.content)["variables"]["cursor"])
        page = next(pages)
        node = {
            "isResolved": True,
            "isOutdated": False,
            "resolvedBy": None,
            "comments": {"nodes": [{"fullDatabaseId": page["id"]}]},
        }
        threads = {"pageInfo": {k: page[k] for k in ("hasNextPage", "endCursor")}, "nodes": [node]}
        body = {"data": {"repository": {"pullRequest": {"reviewThreads": threads}}}}
        return httpx.Response(200, json=body)

    client = GitHubClient(SecretStr("t"), transport=httpx.MockTransport(handler))
    states = GitHubApi(client).list_thread_states(REPO, 7)

    assert [s.root_comment_id for s in states] == [1, 2]
    assert cursors == [None, "abc"]
