"""Pseudonymise a real-world ReviewCase before it is stored in the benchmark.

GitHub logins are replaced by roles: the reviewer who opened the thread becomes ``reviewer``, the
PR author ``author``, anyone else ``participant-N`` (stable within a case). ``@mentions`` of known
logins get the same role. Other ``@words`` are left alone: they are often decorators in suggested
code (``@pytest.mark``). E-mail addresses become ``<email>``.

This limits casual exposure of people's identities; it is not anonymisation: repository, PR and
comment ids are kept as provenance, and the data is public on GitHub.
"""

import re

from verireview.contracts import CommitRef, ReviewCase

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_MENTION = re.compile(r"(?<![\w@])@([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))")


class Pseudonyms:
    def __init__(self, reviewer: str | None, author: str | None) -> None:
        self._roles: dict[str, str] = {}
        self._participants = 0
        if reviewer:
            self._roles[reviewer.lower()] = "reviewer"
        if author and author.lower() not in self._roles:
            self._roles[author.lower()] = "author"

    def role(self, login: str | None) -> str | None:
        if login is None:
            return None
        key = login.lower()
        if key not in self._roles:
            self._participants += 1
            self._roles[key] = f"participant-{self._participants}"
        return self._roles[key]

    def text(self, value: str) -> str:
        value = _EMAIL.sub("<email>", value)
        return _MENTION.sub(self._mention, value)

    def _mention(self, match: re.Match[str]) -> str:
        role = self._roles.get(match.group(1).lower())
        return f"@{role}" if role else match.group(0)


def pseudonymise(case: ReviewCase, pr_author: str | None) -> ReviewCase:
    names = Pseudonyms(case.thread.root.author, pr_author)
    for login in [c.author for c in case.thread.comments] + [case.thread.resolved_by]:
        names.role(login)  # fix role numbering in thread order
    comments = [
        c.model_copy(update={"author": names.role(c.author), "body": names.text(c.body)})
        for c in case.thread.comments
    ]
    thread = case.thread.model_copy(
        update={"comments": comments, "resolved_by": names.role(case.thread.resolved_by)}
    )

    def commits(items: list[CommitRef]) -> list[CommitRef]:
        return [
            c.model_copy(
                update={
                    "author_login": names.role(c.author_login),
                    "message": names.text(c.message),
                }
            )
            for c in items
        ]

    window = case.window.model_copy(
        update={
            "subsequent_commits": commits(case.window.subsequent_commits),
            "ambiguous_rewritten_commits": commits(case.window.ambiguous_rewritten_commits),
            "excluded_pre_comment_commits": commits(case.window.excluded_pre_comment_commits),
        }
    )
    return case.model_copy(
        update={"thread": thread, "window": window, "pull_title": names.text(case.pull_title)}
    )
