from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Collection, Recipe, RecipeCollection
from schemas import RecipeData


def _snapshot(parsed: RecipeData) -> dict[str, Any]:
    return parsed.model_dump(mode="json")


async def create_recipe(
    session: AsyncSession,
    *,
    user_id: str,
    parsed: RecipeData,
    original_html: str | None,
) -> Recipe:
    snapshot = _snapshot(parsed)
    recipe = Recipe(
        user_id=user_id,
        title=parsed.title,
        ingredients=parsed.ingredients,
        instructions=parsed.instructions,
        image=parsed.image,
        prep_time=parsed.prep_time,
        cook_time=parsed.cook_time,
        total_time=parsed.total_time,
        yields=parsed.yields,
        host=parsed.host,
        cuisine=parsed.cuisine,
        category=parsed.category,
        language=parsed.language,
        source_url=parsed.url,
        original_html=original_html,
        parser_method=parsed.method,
        warnings=parsed.warnings,
        parsed_at=datetime.now(),
        parsed_snapshot=snapshot,
    )
    session.add(recipe)
    await session.flush()
    return recipe


async def get_recipe(
    session: AsyncSession, *, user_id: str, recipe_id: str
) -> Recipe | None:
    return await session.scalar(
        select(Recipe).where(Recipe.id == recipe_id, Recipe.user_id == user_id)
    )


_EDITABLE_FIELDS = {
    "title",
    "ingredients",
    "instructions",
    "image",
    "prep_time",
    "cook_time",
    "total_time",
    "yields",
    "host",
    "cuisine",
    "category",
    "language",
    "notes",
}


async def update_recipe(
    session: AsyncSession,
    *,
    user_id: str,
    recipe_id: str,
    updates: dict[str, Any],
) -> Recipe | None:
    recipe = await get_recipe(session, user_id=user_id, recipe_id=recipe_id)
    if recipe is None:
        return None
    for key, value in updates.items():
        if key in _EDITABLE_FIELDS:
            setattr(recipe, key, value)
    await session.flush()
    return recipe


async def delete_recipe(
    session: AsyncSession, *, user_id: str, recipe_id: str
) -> bool:
    recipe = await get_recipe(session, user_id=user_id, recipe_id=recipe_id)
    if recipe is None:
        return False
    await session.delete(recipe)
    await session.flush()
    return True


async def list_recipes(
    session: AsyncSession,
    *,
    user_id: str,
    title_q: str | None = None,
    collection_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Recipe]:
    stmt = select(Recipe).where(Recipe.user_id == user_id)
    if title_q:
        stmt = stmt.where(func.lower(Recipe.title).contains(title_q.lower()))
    if collection_id is not None:
        stmt = (
            stmt.join(RecipeCollection, RecipeCollection.recipe_id == Recipe.id)
            .join(Collection, Collection.id == RecipeCollection.collection_id)
            .where(
                Collection.id == collection_id,
                Collection.user_id == user_id,
            )
        )
    stmt = stmt.order_by(Recipe.created_at.desc()).limit(limit).offset(offset)
    result = await session.scalars(stmt)
    return list(result.all())


async def get_first_duplicate_id(
    session: AsyncSession, *, user_id: str, source_url: str
) -> str | None:
    return await session.scalar(
        select(Recipe.id)
        .where(Recipe.user_id == user_id, Recipe.source_url == source_url)
        .limit(1)
    )


async def count_recipes(
    session: AsyncSession,
    *,
    user_id: str,
    title_q: str | None = None,
    collection_id: str | None = None,
) -> int:
    stmt = select(func.count(Recipe.id)).where(Recipe.user_id == user_id)
    if title_q:
        stmt = stmt.where(func.lower(Recipe.title).contains(title_q.lower()))
    if collection_id is not None:
        stmt = (
            stmt.join(RecipeCollection, RecipeCollection.recipe_id == Recipe.id)
            .join(Collection, Collection.id == RecipeCollection.collection_id)
            .where(Collection.id == collection_id, Collection.user_id == user_id)
        )
    return await session.scalar(stmt) or 0


async def get_recipe_collection_ids(
    session: AsyncSession, *, recipe_id: str
) -> list[str]:
    result = await session.scalars(
        select(RecipeCollection.collection_id).where(
            RecipeCollection.recipe_id == recipe_id
        )
    )
    return list(result.all())


async def create_minimal_recipe(
    session: AsyncSession,
    *,
    user_id: str,
    source_url: str,
    original_html: str | None,
    reason: str,
) -> Recipe:
    recipe = Recipe(
        user_id=user_id,
        source_url=source_url,
        original_html=original_html,
        warnings=[f"parse_failed: {reason}"],
    )
    session.add(recipe)
    await session.flush()
    return recipe
