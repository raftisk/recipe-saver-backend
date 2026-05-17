from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AuthEvent


async def record(
    session: AsyncSession,
    *,
    event_type: str,
    user_id: str | None,
    client_ip: str | None,
) -> None:
    session.add(AuthEvent(event_type=event_type, user_id=user_id, client_ip=client_ip))
    await session.flush()
