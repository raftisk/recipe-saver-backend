from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from api.errors import AppError
from db.models import Session, User
from db.session import get_session
from repositories import sessions as sessions_repo

_bearer = HTTPBearer(auto_error=False)


async def current_session(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> Session:
    if credentials is None:
        raise AppError(401, "unauthorized", "Missing Authorization header.")
    sess = await sessions_repo.get_active_session_by_token(db, credentials.credentials)
    if sess is None:
        raise AppError(401, "unauthorized", "Invalid or expired token.")
    await db.refresh(sess, ["user"])
    return sess


async def current_user(sess: Annotated[Session, Depends(current_session)]) -> User:
    return sess.user


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None
