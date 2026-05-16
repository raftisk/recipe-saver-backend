from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Collection, Recipe, RecipeCollection


class CrossUserError(Exception):
    """Raised when a user tries to link resources owned by another user."""


class DuplicateCollectionName(Exception):
    """Raised when a user tries to create or rename a collection to an existing name."""


async def create_collection(
    session: AsyncSession,
    *,
    user_id: str,
    name: str,
    description: str | None = None,
) -> Collection:
    collection = Collection(user_id=user_id, name=name, description=description)
    session.add(collection)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise DuplicateCollectionName(name) from exc
    return collection


async def get_collection(
    session: AsyncSession, *, user_id: str, collection_id: str
) -> Collection | None:
    return await session.scalar(
        select(Collection).where(
            Collection.id == collection_id, Collection.user_id == user_id
        )
    )


async def list_collections(
    session: AsyncSession, *, user_id: str
) -> list[Collection]:
    result = await session.scalars(
        select(Collection)
        .where(Collection.user_id == user_id)
        .order_by(Collection.name.asc())
    )
    return list(result.all())


async def rename_collection(
    session: AsyncSession,
    *,
    user_id: str,
    collection_id: str,
    new_name: str,
) -> Collection | None:
    collection = await get_collection(
        session, user_id=user_id, collection_id=collection_id
    )
    if collection is None:
        return None
    collection.name = new_name
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise DuplicateCollectionName(new_name) from exc
    return collection


async def delete_collection(
    session: AsyncSession, *, user_id: str, collection_id: str
) -> bool:
    collection = await get_collection(
        session, user_id=user_id, collection_id=collection_id
    )
    if collection is None:
        return False
    await session.delete(collection)
    await session.flush()
    return True


async def add_recipe_to_collection(
    session: AsyncSession,
    *,
    user_id: str,
    recipe_id: str,
    collection_id: str,
) -> bool:
    """Add recipe to collection. Idempotent. Returns True if newly linked, False if already linked.

    Raises CrossUserError if either resource is not owned by user_id, or if either does not exist.
    """
    recipe_owner = await session.scalar(
        select(Recipe.user_id).where(Recipe.id == recipe_id)
    )
    collection_owner = await session.scalar(
        select(Collection.user_id).where(Collection.id == collection_id)
    )
    if recipe_owner != user_id or collection_owner != user_id:
        raise CrossUserError(recipe_id, collection_id)

    existing = await session.scalar(
        select(RecipeCollection).where(
            RecipeCollection.recipe_id == recipe_id,
            RecipeCollection.collection_id == collection_id,
        )
    )
    if existing is not None:
        return False
    session.add(RecipeCollection(recipe_id=recipe_id, collection_id=collection_id))
    await session.flush()
    return True


async def remove_recipe_from_collection(
    session: AsyncSession,
    *,
    user_id: str,
    recipe_id: str,
    collection_id: str,
) -> bool:
    collection = await get_collection(
        session, user_id=user_id, collection_id=collection_id
    )
    if collection is None:
        return False
    link = await session.scalar(
        select(RecipeCollection).where(
            RecipeCollection.recipe_id == recipe_id,
            RecipeCollection.collection_id == collection_id,
        )
    )
    if link is None:
        return False
    await session.delete(link)
    await session.flush()
    return True
