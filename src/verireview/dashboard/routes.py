"""Read-only dashboard pages (Phase 13), served by the API itself.

Owner decisions: server-rendered pages (no JS build), one operator token (off by default), stored
review cases with retention. The pages never write anything except the sign-in cookie.

Every response carries a strict Content-Security-Policy (no scripts at all, styles only from
this service), ``no-store`` caching (pages show private code), no framing and no referrer.
Templates autoescape everything; repository text is only ever rendered as text.
"""

from typing import Annotated, Any
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape
from sqlalchemy.orm import Session

from verireview.config import get_settings
from verireview.dashboard import auth, present, queries
from verireview.db.session import get_session
from verireview.gh.api import RepoRef

router = APIRouter(prefix="/dashboard", include_in_schema=False)

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'self'; img-src 'self'; form-action 'self'; "
        "frame-ancestors 'none'; base-uri 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}
_env = Environment(
    loader=PackageLoader("verireview.dashboard", "templates"),
    autoescape=select_autoescape(default=True, default_for_string=True),
    undefined=StrictUndefined,
)
DB = Annotated[Session, Depends(get_session)]


def _with_headers(response: Response) -> Response:
    response.headers.update(SECURITY_HEADERS)
    return response


def _render(template: str, status: int = 200, **context: Any) -> Response:
    html = _env.get_template(template).render(**context)
    return _with_headers(HTMLResponse(html, status_code=status))


def _not_found() -> Response:
    return _render("error.html", 404, title="Not found", message="Nothing here.")


def _guard(request: Request) -> Response | None:
    """404 when the dashboard is off; to the sign-in page without a valid session."""
    token = get_settings().dashboard_token
    if token is None:
        return _with_headers(Response(status_code=404))
    if not auth.session_valid(token, request.cookies.get(auth.COOKIE)):
        return _with_headers(RedirectResponse("/dashboard/login", status_code=303))
    return None


# ---------------------------------------------------------------- sign-in


@router.get("/login")
def login_form(request: Request) -> Response:
    if get_settings().dashboard_token is None:
        return _with_headers(Response(status_code=404))
    return _render("login.html", title="Sign in", error=None)


@router.post("/login")
async def login(request: Request) -> Response:
    settings = get_settings()
    token = settings.dashboard_token
    if token is None:
        return _with_headers(Response(status_code=404))
    client = request.client.host if request.client else "unknown"
    if auth.limiter.blocked(client):
        return _render("login.html", 429, title="Sign in", error="Too many attempts; wait.")
    fields = parse_qs((await request.body()).decode("utf-8", errors="replace")[:4096])
    candidate = (fields.get("token") or [""])[0]
    if not auth.token_matches(token, candidate):
        auth.limiter.fail(client)
        return _render("login.html", 401, title="Sign in", error="Wrong token.")
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie(
        auth.COOKIE,
        auth.issue_session(token, settings.dashboard_session_hours),
        max_age=settings.dashboard_session_hours * 3600,
        path="/dashboard",
        httponly=True,
        samesite="strict",
        secure=request.url.scheme == "https",
    )
    return _with_headers(response)


@router.post("/logout")
def logout() -> Response:
    response = RedirectResponse("/dashboard/login", status_code=303)
    response.delete_cookie(auth.COOKIE, path="/dashboard")
    return _with_headers(response)


@router.get("/static/style.css")
def stylesheet() -> Response:
    css = _env.loader.get_source(_env, "style.css")[0] if _env.loader else ""
    return _with_headers(Response(css, media_type="text/css"))


# ---------------------------------------------------------------- pages


@router.get("")
def overview(request: Request, session: DB) -> Response:
    if (denied := _guard(request)) is not None:
        return denied
    from verireview.enforcement.eligibility import load_shipped

    settings = get_settings()
    try:
        gate = load_shipped()
    except (OSError, ValueError):
        gate = None
    return _render(
        "overview.html",
        title="Overview",
        repositories=queries.repositories(session),
        verdicts=queries.verdict_totals(session),
        jobs=queries.job_totals(session),
        gate=gate,
        allow_block=settings.policy_allow_block,
        retention_days=settings.audit_retention_days,
    )


@router.get("/r/{installation}/{owner}/{name}")
def repository(request: Request, session: DB, installation: int, owner: str, name: str) -> Response:
    if (denied := _guard(request)) is not None:
        return denied
    repo = _repo(owner, name)
    if repo is None:
        return _not_found()
    return _render(
        "repository.html",
        title=repo,
        installation=installation,
        repository=repo,
        policy=queries.policy(session, installation, repo),
        changes=queries.policy_changes(session, installation, repo),
        confirmations=queries.confirmations(session, installation, repo),
        pulls=queries.pulls(session, installation, repo),
    )


@router.get("/r/{installation}/{owner}/{name}/pull/{number}")
def pull(
    request: Request, session: DB, installation: int, owner: str, name: str, number: int
) -> Response:
    if (denied := _guard(request)) is not None:
        return denied
    repo = _repo(owner, name)
    histories = queries.threads(session, installation, repo, number) if repo else []
    if repo is None or not histories:
        return _not_found()
    return _render(
        "pull.html",
        title=f"{repo}#{number}",
        installation=installation,
        repository=repo,
        number=number,
        threads=histories,
    )


@router.get("/audit/{audit_id}")
def audit(request: Request, session: DB, audit_id: int) -> Response:
    if (denied := _guard(request)) is not None:
        return denied
    row = queries.audit(session, audit_id)
    if row is None:
        return _not_found()
    return _render(
        "audit.html",
        title=f"Verification {row.id}",
        row=row,
        detail=present.detail(row.result, row.review_case),
    )


@router.get("/jobs")
def jobs(request: Request, session: DB) -> Response:
    if (denied := _guard(request)) is not None:
        return denied
    return _render("jobs.html", title="Jobs", jobs=queries.recent_jobs(session))


def _repo(owner: str, name: str) -> str | None:
    try:
        return RepoRef(f"{owner}/{name}").full_name
    except ValueError:
        return None
