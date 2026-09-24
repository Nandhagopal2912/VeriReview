"""POST /github/webhook: signed GitHub App deliveries → advisory jobs (Phase 11).

Order matters: size limit, then the signature over the raw body, and only then parsing. An
unsigned or forged delivery is rejected with 401 before its content is looked at. Without a
configured webhook secret the endpoint refuses everything (503) rather than accept unsigned
input. Work is queued, not done here: GitHub expects an answer within 10 seconds, and a
redelivery with the same ``X-GitHub-Delivery`` id queues nothing new (idempotency).
"""

import json
import logging
import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from verireview.advisory.jobs import enqueue
from verireview.advisory.webhooks import InvalidSignatureError, tasks_from_event, verify_signature
from verireview.config import get_settings
from verireview.db.session import get_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/github", tags=["github"])

MAX_BODY_BYTES = 5 * 1024 * 1024
_DELIVERY = re.compile(r"^[A-Za-z0-9-]{1,100}$")
_EVENT = re.compile(r"^[a-z_]{1,60}$")


class WebhookResponse(BaseModel):
    status: str  # "queued" | "duplicate" | "ignored" | "pong"
    jobs: int = 0


@router.post("/webhook", status_code=status.HTTP_202_ACCEPTED, response_model=WebhookResponse)
async def github_webhook(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    x_github_event: Annotated[str, Header()],
    x_github_delivery: Annotated[str, Header()],
    x_hub_signature_256: Annotated[str | None, Header()] = None,
) -> WebhookResponse:
    settings = get_settings()
    if settings.github_webhook_secret is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "webhook secret not configured")
    if not _DELIVERY.match(x_github_delivery) or not _EVENT.match(x_github_event):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "malformed GitHub headers")

    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "payload too large")
    try:
        verify_signature(
            settings.github_webhook_secret.get_secret_value(), body, x_hub_signature_256
        )
    except InvalidSignatureError as exc:
        logger.warning("rejected webhook delivery %s: %s", x_github_delivery, exc)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid signature") from exc

    if x_github_event == "ping":
        return WebhookResponse(status="pong")
    try:
        payload: Any = json.loads(body)
        tasks = tasks_from_event(x_github_event, payload, settings.advisory_check_name)
    except (ValueError, ValidationError, AttributeError, TypeError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "unexpected payload") from exc
    if not tasks:
        return WebhookResponse(status="ignored")

    created = await run_in_threadpool(enqueue, session, x_github_delivery, x_github_event, tasks)
    logger.info(
        "webhook %s (%s): %d job(s) queued of %d",
        x_github_delivery,
        x_github_event,
        created,
        len(tasks),
    )
    return WebhookResponse(status="queued" if created else "duplicate", jobs=created)
