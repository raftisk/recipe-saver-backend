import time
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import client_ip, current_user
from api.errors import AppError
from config import settings
from db.models import User
from db.session import get_session
from repositories import recipes as recipes_repo
from scraper import scrape_from_html, scrape_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/recipes", tags=["recipes"])


class SaveRecipeBody(BaseModel):
    url: str
    html: str


class ParseUrlBody(BaseModel):
    url: str


class RecipeOut(BaseModel):
    id: str
    user_id: str
    title: str | None
    ingredients: list[str] | None
    instructions: str | None
    image: str | None
    prep_time: int | None
    cook_time: int | None
    total_time: int | None
    yields: str | None
    host: str | None
    cuisine: str | None
    category: str | None
    language: str | None
    source_url: str
    parser_method: str | None
    warnings: list[str] | None
    notes: str | None
    collection_ids: list[str] = []

    model_config = {"from_attributes": True}


class RecipeListOut(BaseModel):
    items: list[RecipeOut]
    total: int
    limit: int
    offset: int


class SaveRecipeOut(BaseModel):
    recipe: RecipeOut
    partial: bool = False
    duplicate_of: str | None = None


def _recipe_out(recipe, collection_ids: list[str] | None = None) -> dict[str, Any]:
    return RecipeOut(
        id=recipe.id,
        user_id=recipe.user_id,
        title=recipe.title,
        ingredients=recipe.ingredients,
        instructions=recipe.instructions,
        image=recipe.image,
        prep_time=recipe.prep_time,
        cook_time=recipe.cook_time,
        total_time=recipe.total_time,
        yields=recipe.yields,
        host=recipe.host,
        cuisine=recipe.cuisine,
        category=recipe.category,
        language=recipe.language,
        source_url=recipe.source_url,
        parser_method=recipe.parser_method,
        warnings=recipe.warnings,
        notes=recipe.notes,
        collection_ids=collection_ids or [],
    ) # type: ignore


@router.post("", response_model=SaveRecipeOut, status_code=201)
async def save_recipe(
    body: SaveRecipeBody,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    if len(body.html.encode()) > settings.max_html_bytes:
        raise AppError(413, "payload_too_large", "HTML exceeds 2 MiB limit.")

    t0 = time.monotonic()
    partial = False
    recipe = None

    try:
        parsed = scrape_from_html(body.html, body.url)
        recipe = await recipes_repo.create_recipe(
            db, user_id=user.id, parsed=parsed, original_html=body.html
        )
    except Exception as exc:
        partial = True
        recipe = await recipes_repo.create_minimal_recipe(
            db,
            user_id=user.id,
            source_url=body.url,
            original_html=body.html,
            reason=str(exc),
        )

    duplicate_of = await recipes_repo.get_first_duplicate_id(
        db, user_id=user.id, source_url=body.url
    )
    # exclude the just-saved recipe itself
    if duplicate_of == recipe.id:
        duplicate_of = None

    latency_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        "recipe_saved user=%s url=%s method=%s warnings=%d partial=%s latency_ms=%d",
        user.id,
        body.url,
        recipe.parser_method,
        len(recipe.warnings or []),
        partial,
        latency_ms,
    )

    await db.commit()
    collection_ids = await recipes_repo.get_recipe_collection_ids(db, recipe_id=recipe.id)
    return SaveRecipeOut(
        recipe=_recipe_out(recipe, collection_ids), # type: ignore
        partial=partial,
        duplicate_of=duplicate_of,
    )


@router.get("", response_model=RecipeListOut)
async def list_recipes(
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
    q: str | None = Query(default=None),
    collection_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    recipes = await recipes_repo.list_recipes(
        db, user_id=user.id, title_q=q, collection_id=collection_id,
        limit=limit, offset=offset,
    )
    total = await recipes_repo.count_recipes(
        db, user_id=user.id, title_q=q, collection_id=collection_id,
    )
    items = [_recipe_out(r) for r in recipes]
    return RecipeListOut(items=items, total=total, limit=limit, offset=offset) # type: ignore


@router.get("/{recipe_id}", response_model=RecipeOut)
async def get_recipe(
    recipe_id: str,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    recipe = await recipes_repo.get_recipe(db, user_id=user.id, recipe_id=recipe_id)
    if recipe is None:
        raise AppError(404, "not_found", "Recipe not found.")
    collection_ids = await recipes_repo.get_recipe_collection_ids(db, recipe_id=recipe.id)
    return _recipe_out(recipe, collection_ids)


class PatchRecipeBody(BaseModel):
    title: str | None = None
    ingredients: list[str] | None = None
    instructions: str | None = None
    image: str | None = None
    prep_time: int | None = None
    cook_time: int | None = None
    total_time: int | None = None
    yields: str | None = None
    host: str | None = None
    cuisine: str | None = None
    category: str | None = None
    language: str | None = None
    notes: str | None = None


@router.patch("/{recipe_id}", response_model=RecipeOut)
async def patch_recipe(
    recipe_id: str,
    body: PatchRecipeBody,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    updates = body.model_dump(exclude_unset=True)
    recipe = await recipes_repo.update_recipe(
        db, user_id=user.id, recipe_id=recipe_id, updates=updates
    )
    if recipe is None:
        raise AppError(404, "not_found", "Recipe not found.")
    await db.commit()
    collection_ids = await recipes_repo.get_recipe_collection_ids(db, recipe_id=recipe.id)
    return _recipe_out(recipe, collection_ids)


@router.delete("/{recipe_id}", status_code=204)
async def delete_recipe(
    recipe_id: str,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    deleted = await recipes_repo.delete_recipe(db, user_id=user.id, recipe_id=recipe_id)
    if not deleted:
        raise AppError(404, "not_found", "Recipe not found.")
    await db.commit()


@router.post("/parse-url", response_model=dict)
async def parse_url(
    body: ParseUrlBody,
    user: Annotated[User, Depends(current_user)],
):
    return scrape_url(body.url).model_dump()
