from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import client_ip, current_session, current_user
from api.errors import AppError
from auth.passwords import hash_password, validate_password_policy, verify_password
from db.models import Session, User
from db.session import get_session
from repositories import auth_events as events_repo
from repositories import sessions as sessions_repo
from repositories import users as users_repo

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class AuthBody(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: str
    email: str


class TokenResponse(BaseModel):
    user: UserOut
    token: str
    expires_at: str


@router.post("/register", status_code=201, response_model=TokenResponse)
async def register(
    body: AuthBody,
    db: Annotated[AsyncSession, Depends(get_session)],
    ip: Annotated[str | None, Depends(client_ip)],
):
    policy_err = validate_password_policy(body.password)
    if policy_err:
        raise AppError(400, "auth_failed", policy_err)

    if await users_repo.get_user_by_email(db, body.email):
        raise AppError(400, "auth_failed", "Registration failed.")

    user = await users_repo.create_user(
        db, email=body.email, password_hash=hash_password(body.password)
    )
    sess, raw_token = await sessions_repo.create_session(db, user_id=user.id)
    await events_repo.record(db, event_type="register", user_id=user.id, client_ip=ip)
    await db.commit()

    return TokenResponse(
        user=UserOut(id=user.id, email=user.email),
        token=raw_token,
        expires_at=sess.expires_at.isoformat(),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: AuthBody,
    db: Annotated[AsyncSession, Depends(get_session)],
    ip: Annotated[str | None, Depends(client_ip)],
):
    user = await users_repo.get_user_by_email(db, body.email)
    if user is None or not verify_password(body.password, user.password_hash):
        await events_repo.record(
            db,
            event_type="login_failure",
            user_id=user.id if user else None,
            client_ip=ip,
        )
        await db.commit()
        raise AppError(400, "auth_failed", "Login failed.")

    await users_repo.touch_last_sign_in(db, user)
    sess, raw_token = await sessions_repo.create_session(db, user_id=user.id)
    await events_repo.record(db, event_type="login_success", user_id=user.id, client_ip=ip)
    await db.commit()

    return TokenResponse(
        user=UserOut(id=user.id, email=user.email),
        token=raw_token,
        expires_at=sess.expires_at.isoformat(),
    )


@router.post("/logout", status_code=204)
async def logout(
    calling_session: Annotated[Session, Depends(current_session)],
    db: Annotated[AsyncSession, Depends(get_session)],
    ip: Annotated[str | None, Depends(client_ip)],
):
    await sessions_repo.revoke_session(db, calling_session)
    await events_repo.record(
        db, event_type="logout", user_id=calling_session.user_id, client_ip=ip
    )
    await db.commit()


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[User, Depends(current_user)]):
    return UserOut(id=user.id, email=user.email)


@router.post("/extension-token", response_model=TokenResponse, status_code=201)
async def extension_token(
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
    ip: Annotated[str | None, Depends(client_ip)],
):
    sess, raw_token = await sessions_repo.create_session(db, user_id=user.id, client="extension")
    await events_repo.record(db, event_type="extension_handoff", user_id=user.id, client_ip=ip)
    await db.commit()
    return TokenResponse(
        user=UserOut(id=user.id, email=user.email),
        token=raw_token,
        expires_at=sess.expires_at.isoformat(),
    )
