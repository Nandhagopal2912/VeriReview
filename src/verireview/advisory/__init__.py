"""GitHub advisory mode (Phase 11): App auth, signed webhooks, job queue, neutral Check Runs.

Advisory only: the published check's conclusion is always ``neutral`` and never blocks a merge.
"""

from verireview.advisory.auth import INSTALLATION_PERMISSIONS, AppAuthError, GitHubAppAuth
from verireview.advisory.checks import CONCLUSION
from verireview.advisory.webhooks import (
    AdvisoryTask,
    InvalidSignatureError,
    sign,
    tasks_from_event,
    verify_signature,
)

__all__ = [
    "CONCLUSION",
    "INSTALLATION_PERMISSIONS",
    "AdvisoryTask",
    "AppAuthError",
    "GitHubAppAuth",
    "InvalidSignatureError",
    "sign",
    "tasks_from_event",
    "verify_signature",
]
