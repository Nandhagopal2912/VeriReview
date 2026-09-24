"""The "VeriReview" Check Run: one check per pull-request head.

Its conclusion is ``neutral`` (owner decision, Phase 11) unless **all** Phase 12 locks are open:
the repository opted in to the ``enforcement`` stage, the global ``policy_allow_block`` is on, and
a verified thread's audited action is BLOCK, which the policy only gives when every failed
requirement is in an enforced category that the frozen test evidence makes eligible (none today).
Only then is it ``failure``, and even that blocks a merge only if the repository requires the
check in branch protection. In the ``human_review`` stage the check carries a "Confirm reviewed"
button; confirmations are recorded and listed.

Text that comes from the repository (requirement wording, file names, evidence quoting code) is
untrusted. It only ever appears inside a fenced ``text`` block (with any fence inside it broken),
where Markdown renders nothing: no links, images, HTML or @-mentions. Everything outside the
fence is built from validated values only (verdict names, numbers, the repository name).
"""

import re
from collections.abc import Sequence
from typing import Any

from verireview.advisory.webhooks import CONFIRM_ACTION
from verireview.db.models import VerificationAudit
from verireview.gh.api import RepoRef
from verireview.gh.client import GitHubClient
from verireview.policy import Action, OperatingMode, PolicyConfig

NEUTRAL, FAILURE = "neutral", "failure"
CONCLUSION = NEUTRAL  # the conclusion unless every enforcement lock is open
CONFIRM_BUTTON = {
    "label": "Confirm reviewed",
    "description": "I reviewed the flagged threads",
    "identifier": CONFIRM_ACTION,
}
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


def conclusion_for(rows: Sequence[VerificationAudit], policy: PolicyConfig) -> str:
    """``failure`` only when enforcing (stage + global switch) and an audited action is BLOCK."""
    enforcing = policy.mode == OperatingMode.ENFORCEMENT and policy.allow_block
    blocked = any(row.action == Action.BLOCK.value for row in rows)
    return FAILURE if enforcing and blocked else NEUTRAL


def render(
    repo: RepoRef,
    pull_number: int,
    rows: Sequence[VerificationAudit],
    policy: PolicyConfig | None = None,
    reviewers: Sequence[str] = (),
) -> dict[str, str]:
    """Check Run ``output`` (title, summary, text) for the verified threads at one head."""
    policy = policy or PolicyConfig()
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.verdict] = counts.get(row.verdict, 0) + 1
    title = f"{len(rows)} resolved thread(s) checked: " + ", ".join(
        f"{n} {verdict.lower().replace('_', ' ')}" for verdict, n in sorted(counts.items())
    )
    lines = [_stage_header(policy), ""]
    if policy.mode == OperatingMode.HUMAN_REVIEW:
        confirmed = ", ".join(f"`{r}`" for r in reviewers) or "nobody yet"
        lines += [
            "**Human review.** A reviewer should look at the flagged threads and press "
            f"*Confirm reviewed*. Confirmed by: {confirmed}.",
            "",
        ]
    lines += ["| Thread | Result | Confidence | Suggested |", "|---|---|---|---|"]
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


def _stage_header(policy: PolicyConfig) -> str:
    if policy.mode != OperatingMode.ENFORCEMENT or not policy.allow_block:
        return HEADER
    categories = ", ".join(sorted(c.value for c in policy.enforced_categories)) or "none"
    return (
        f"**Enforcement for: {categories}.** This check fails only when a thread whose failed "
        "requirements are all in these categories is judged not satisfied with medium "
        "confidence; everything else is advisory. It blocks merging only if the repository "
        "requires this check."
    )


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
    client: GitHubClient,
    repo: RepoRef,
    head_sha: str,
    name: str,
    output: dict[str, str],
    conclusion: str = NEUTRAL,
    confirm_button: bool = False,
) -> int:
    """Create the check run on ``head_sha``, or update ours if it exists; returns its id."""
    if conclusion not in (NEUTRAL, FAILURE):
        raise ValueError(f"unsupported conclusion {conclusion!r}")
    body: dict[str, object] = {"status": "completed", "conclusion": conclusion, "output": output}
    body["actions"] = [CONFIRM_BUTTON] if confirm_button else []
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
