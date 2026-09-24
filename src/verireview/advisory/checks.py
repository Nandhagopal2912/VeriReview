"""The advisory Check Run: one "VeriReview" check per pull-request head, never blocking.

The conclusion is always ``neutral`` (owner decision, Phase 11). It is a constant, and nothing
here accepts another value, so no configuration can make the check fail or block a merge.
Blocking stays a Phase 12 question (policy_allow_block, pinned off by a test).

Text that comes from the repository (requirement wording, file names, evidence quoting code) is
untrusted. It only ever appears inside a fenced ``text`` block (with any fence inside it broken),
where Markdown renders nothing: no links, images, HTML or @-mentions. Everything outside the
fence is built from validated values only (verdict names, numbers, the repository name).
"""

import re
from collections.abc import Sequence
from typing import Any

from verireview.db.models import VerificationAudit
from verireview.gh.api import RepoRef
from verireview.gh.client import GitHubClient

CONCLUSION = "neutral"
MAX_OUTPUT_CHARS = 60_000  # GitHub's limit is 65,535 per field
_FENCE = re.compile(r"`{3,}|~{3,}")

HEADER = (
    "**Advisory only.** This check never fails and never blocks merging. VeriReview checks "
    "whether each resolved review thread was actually addressed, from the code changed after "
    "the comment. On its latest blind benchmark it was right about 2 times in 3 and accepted "
    "about 1 in 7 unaddressed threads, so use it as a pointer for reviewers, not as a gate."
)
_ACTION_TEXT = {
    "ALLOW": "no action needed",
    "WARN": "look at it",
    "HUMAN_REVIEW": "human review",
    "BLOCK": "look at it",  # never reached in advisory mode; kept as text, not as a conclusion
}
_ICON = {
    "SATISFIED": "✅",
    "PARTIALLY_SATISFIED": "🟡",
    "NOT_SATISFIED": "❌",
    "UNCERTAIN": "❔",
}


def render(repo: RepoRef, pull_number: int, rows: Sequence[VerificationAudit]) -> dict[str, str]:
    """Check Run ``output`` (title, summary, text) for the verified threads at one head."""
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.verdict] = counts.get(row.verdict, 0) + 1
    title = f"{len(rows)} resolved thread(s) checked: " + ", ".join(
        f"{n} {verdict.lower().replace('_', ' ')}" for verdict, n in sorted(counts.items())
    )
    lines = [HEADER, "", "| Thread | Result | Confidence | Suggested |", "|---|---|---|---|"]
    for row in rows:
        link = (
            f"https://github.com/{repo.full_name}/pull/{pull_number}#discussion_r{row.comment_id}"
        )
        lines.append(
            f"| [comment {row.comment_id}]({link}) | {_ICON.get(row.verdict, '')} "
            f"{row.verdict} | {row.confidence} | {_ACTION_TEXT.get(row.action, row.action)} |"
        )
    lines += [
        "",
        f"Pipeline `{rows[0].pipeline_version if rows else '-'}`. Details per thread below; "
        "evidence lines cite the file, lines and commit they are based on.",
    ]
    details = [_details(row) for row in rows]
    return {
        "title": title[:250],
        "summary": _limit("\n".join(lines)),
        "text": _limit("\n\n".join(details)),
    }


def _details(row: VerificationAudit) -> str:
    result: dict[str, Any] = row.result
    explanation = _FENCE.sub("'''", str(result.get("explanation", "")))
    return (
        f"### Comment {row.comment_id}: {row.verdict} ({row.confidence})\n\n"
        f"```text\n{explanation}\n```"
    )


def _limit(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    cut = text[: MAX_OUTPUT_CHARS - 40]
    if cut.count("```") % 2:  # do not leave a fence open
        cut += "\n```"
    return cut + "\n\n…(truncated)"


def publish(
    client: GitHubClient, repo: RepoRef, head_sha: str, name: str, output: dict[str, str]
) -> int:
    """Create the check run on ``head_sha``, or update ours if it exists; returns its id."""
    body = {"status": "completed", "conclusion": CONCLUSION, "output": output}
    existing = client.get_json(
        f"/repos/{repo.full_name}/commits/{head_sha}/check-runs",
        params={"check_name": name, "filter": "latest"},
    )
    runs = existing.get("check_runs", []) if isinstance(existing, dict) else []
    if runs:
        run_id = int(runs[0]["id"])
        client.patch_json(f"/repos/{repo.full_name}/check-runs/{run_id}", body)
        return run_id
    created = client.post_json(
        f"/repos/{repo.full_name}/check-runs", {"name": name, "head_sha": head_sha, **body}
    )
    return int(created["id"])
