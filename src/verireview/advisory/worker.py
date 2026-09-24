"""The advisory worker: claim a job, verify, audit, publish the neutral Check Run.

For each job it gets an installation token scoped to the job's repository, re-reads the pull
request from GitHub (never trusting the webhook body for anything but ids), ingests the review
thread(s), runs the default pipeline, applies the policy, writes an audit row per thread, and
updates the check on the head commit that was verified. In OBSERVE mode it audits but posts
nothing.

Failures: GitHub outages, rate limits and auth problems are retried with backoff; a thread or
pull request that does not exist fails the job at once. Error text stored on the job is the
exception's class and message, which never contains tokens (the client puts only API paths in
its messages).
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from verireview.advisory import checks
from verireview.advisory.auth import AppAuthError, GitHubAppAuth
from verireview.advisory.jobs import claim, complete, latest_results, record_audit, retry_or_fail
from verireview.db.models import AdvisoryJob
from verireview.gh.api import GitHubApi, RepoRef
from verireview.gh.errors import GitHubError, GitHubNotFoundError
from verireview.ingestion import ingest_review_case
from verireview.policy import OperatingMode, PolicyConfig, decide
from verireview.threads import ThreadNotFoundError
from verireview.verification import DEFAULT_PIPELINE, get_pipeline

logger = logging.getLogger(__name__)

PERMANENT_ERRORS = (GitHubNotFoundError, ThreadNotFoundError, ValueError)
RETRYABLE_ERRORS = (GitHubError, AppAuthError)


@dataclass
class AdvisoryWorker:
    auth: GitHubAppAuth
    sessions: sessionmaker[Session]
    policy: PolicyConfig
    check_name: str = "VeriReview"
    pipeline: str = DEFAULT_PIPELINE
    max_attempts: int = 3

    def run_once(self) -> bool:
        """Process one job if there is one; returns whether a job was taken."""
        with self.sessions() as session:
            job = claim(session)
            if job is None:
                return False
            try:
                self.process(session, job)
            except PERMANENT_ERRORS as exc:
                logger.warning("advisory job %s failed permanently: %s", job.id, type(exc).__name__)
                retry_or_fail(session, job, _describe(exc), self.max_attempts, permanent=True)
            except RETRYABLE_ERRORS as exc:
                logger.warning("advisory job %s failed, will retry: %s", job.id, type(exc).__name__)
                retry_or_fail(session, job, _describe(exc), self.max_attempts)
            else:
                complete(session, job)
            return True

    def run_forever(
        self, poll_interval_s: float, sleep: Callable[[float], None] = time.sleep
    ) -> None:
        logger.info(
            "advisory worker started (check %r, mode %s)", self.check_name, self.policy.mode
        )
        while True:
            if not self.run_once():
                sleep(poll_interval_s)

    def process(self, session: Session, job: AdvisoryJob) -> None:
        repo = RepoRef(job.repository)
        pipeline = get_pipeline(self.pipeline)
        with self.auth.client_for(job.installation_id, repo) as client:
            reader = GitHubApi(client)
            comment_ids = (
                [job.comment_id]
                if job.kind == "thread" and job.comment_id is not None
                else _resolved_threads(reader, repo, job.pull_number)
            )
            head = job.head_sha
            for comment_id in comment_ids:
                case = ingest_review_case(reader, repo, job.pull_number, comment_id)
                result = pipeline.run(case)
                decision = decide(result, self.policy)
                record_audit(session, job, case, comment_id, result, decision)
                head = case.head_sha
                logger.info(
                    "advisory job %s: %s#%s comment %s -> %s (%s)",
                    job.id,
                    repo.full_name,
                    job.pull_number,
                    comment_id,
                    result.verdict.value,
                    result.confidence.value,
                )
            if head is None:
                head = reader.get_pull(repo, job.pull_number).head.sha
            if self.policy.mode == OperatingMode.OBSERVE:
                return  # observe: analyse and audit only, post nothing (plan §27)
            rows = latest_results(
                session, job.installation_id, job.repository, job.pull_number, head
            )
            if rows:
                output = checks.render(repo, job.pull_number, rows)
                checks.publish(client, repo, head, self.check_name, output)


def _resolved_threads(reader: GitHubApi, repo: RepoRef, pull_number: int) -> list[int]:
    return [
        s.root_comment_id for s in reader.list_thread_states(repo, pull_number) if s.is_resolved
    ]


def _describe(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"
