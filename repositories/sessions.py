import hashlib
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.models import Session


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now()


async def create_session(
    session: AsyncSession, *, user_id: str, client: str = "web"
) -> tuple[Session, str]:
    raw_token = secrets.token_urlsafe(32)
    expires_at = _now() + timedelta(days=settings.session_ttl_days)
    sess = Session(
        user_id=user_id,
        token_hash=_hash_token(raw_token),
        client=client,
        expires_at=expires_at,
        last_used_at=_now(),
    )
    session.add(sess)
    await session.flush()
    return sess, raw_token


async def get_active_session_by_token(
    session: AsyncSession, raw_token: str
) -> Session | None:
    now = _now()
    token_hash = _hash_token(raw_token)
    sess = await session.scalar(
        select(Session).where(
            Session.token_hash == token_hash,
            Session.revoked_at.is_(None),
            Session.expires_at > now,
        )
    )
    if sess is None:
        return None

    # sliding window: extend if within the window of expiry
    window = timedelta(days=settings.session_sliding_window_days)
    sess.last_used_at = now
    if sess.expires_at - now < window:
        sess.expires_at = now + timedelta(days=settings.session_ttl_days)
    await session.flush()
    return sess


async def revoke_session(session: AsyncSession, sess: Session) -> None:
    sess.revoked_at = _now()
    await session.flush()

