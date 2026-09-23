"""Verification endpoints.

POST /verify          a ReviewCase (e.g. from `verireview ingest`) → result + policy decision
POST /verify/github   OWNER/REPO + PR + comment id → ingest from GitHub, then verify
"""

from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from verireview.config import get_settings
from verireview.contracts import ReviewCase, VerificationResult
from verireview.gh.api import GitHubApi, GitHubReader, RepoRef
from verireview.gh.client import GitHubClient
from verireview.gh.errors import GitHubError, GitHubNotFoundError, GitHubRateLimitedError
from verireview.ingestion import ingest_review_case
from verireview.policy import PolicyConfig, PolicyDecision, configured_policy, decide
from verireview.threads import ThreadNotFoundError
from verireview.verification import DEFAULT_PIPELINE, PIPELINES, get_pipeline

router = APIRouter(prefix="/verify", tags=["verification"])


class _PipelineChoice(BaseModel):
    pipeline: str = DEFAULT_PIPELINE

    @field_validator("pipeline")
    @classmethod
    def _known(cls, value: str) -> str:
        if value not in PIPELINES:
            raise ValueError(f"unknown pipeline {value!r}; choose from {sorted(PIPELINES)}")
        return value


class VerifyRequest(_PipelineChoice):
    case: ReviewCase


class GitHubVerifyRequest(_PipelineChoice):
    repository: str = Field(description="'owner/repo'")
    pull_number: int = Field(gt=0)
    comment_id: int = Field(gt=0, description="Any comment of the review thread.")

    @field_validator("repository")
    @classmethod
    def _repo(cls, value: str) -> str:
        RepoRef(value)  # raises ValueError on anything but owner/repo
        return value


class VerifyResponse(BaseModel):
    result: VerificationResult
    policy: PolicyDecision


def get_github_reader() -> Iterator[GitHubReader]:
    settings = get_settings()
    client = GitHubClient(
        settings.github_token,
        api_url=settings.github_api_url,
        timeout_s=settings.github_timeout_s,
        max_retries=settings.github_max_retries,
    )
    with client:
        yield GitHubApi(client)


Policy = Annotated[PolicyConfig, Depends(configured_policy)]
Reader = Annotated[GitHubReader, Depends(get_github_reader)]


@router.post("", response_model=VerifyResponse)
def verify(request: VerifyRequest, policy: Policy) -> VerifyResponse:
    return _verify(request.case, request.pipeline, policy)


@router.post("/github", response_model=VerifyResponse)
def verify_github(request: GitHubVerifyRequest, policy: Policy, reader: Reader) -> VerifyResponse:
    try:
        case = ingest_review_case(
            reader, RepoRef(request.repository), request.pull_number, request.comment_id
        )
    except (GitHubNotFoundError, ThreadNotFoundError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except GitHubRateLimitedError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except GitHubError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return _verify(case, request.pipeline, policy)


def _verify(case: ReviewCase, pipeline: str, policy: PolicyConfig) -> VerifyResponse:
    try:
        result = get_pipeline(pipeline).run(case)
    except ModuleNotFoundError as exc:  # e.g. phase7-semantic without the optional `nlp` group
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            f"pipeline {pipeline!r} needs the optional `nlp` dependency group "
            f"(missing module {exc.name!r}), which this service does not install",
        ) from exc
    return VerifyResponse(result=result, policy=decide(result, policy))
