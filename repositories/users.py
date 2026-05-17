from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User


async def create_user(
    session: AsyncSession, *, email: str, password_hash: str
) -> User:
    user = User(email=email.strip().lower(), password_hash=password_hash)
    session.add(user)
    await session.flush()
    return user


async def get_user(session: AsyncSession, user_id: str) -> User | None:
    return await session.scalar(select(User).where(User.id == user_id))


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(
        select(User).where(User.email == email.strip().lower())
    )


async def update_password(session: AsyncSession, user: User, new_hash: str) -> None:
    user.password_hash = new_hash
    await session.flush()


async def touch_last_sign_in(session: AsyncSession, user: User) -> None:
    from datetime import datetime, timezone
    user.last_sign_in_at = datetime.now(timezone.utc)
    await session.flush()
