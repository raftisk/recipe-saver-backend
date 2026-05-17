from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import current_user
from api.errors import AppError
from db.models import User
from db.session import get_session
from repositories import collections as collections_repo
from repositories.collections import CrossUserError, DuplicateCollectionName

router = APIRouter(prefix="/api/v1/collections", tags=["collections"])


class CollectionBody(BaseModel):
    name: str
    description: str | None = None


class PatchCollectionBody(BaseModel):
    name: str | None = None
    description: str | None = None


class CollectionOut(BaseModel):
    id: str
    user_id: str
    name: str
    description: str | None

    model_config = {"from_attributes": True}


def _out(c) -> CollectionOut:
    return CollectionOut(id=c.id, user_id=c.user_id, name=c.name, description=c.description)


@router.post("", response_model=CollectionOut, status_code=201)
async def create_collection(
    body: CollectionBody,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    try:
        col = await collections_repo.create_collection(
            db, user_id=user.id, name=body.name, description=body.description
        )
    except DuplicateCollectionName:
        raise AppError(409, "collection_name_taken", "A collection with that name already exists.")
    await db.commit()
    return _out(col)


@router.get("", response_model=list[CollectionOut])
async def list_collections(
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    cols = await collections_repo.list_collections(db, user_id=user.id)
    return [_out(c) for c in cols]


@router.patch("/{collection_id}", response_model=CollectionOut)
async def patch_collection(
    collection_id: str,
    body: PatchCollectionBody,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    col = await collections_repo.get_collection(db, user_id=user.id, collection_id=collection_id)
    if col is None:
        raise AppError(404, "not_found", "Collection not found.")
    if body.name is not None:
        try:
            col = await collections_repo.rename_collection(
                db, user_id=user.id, collection_id=collection_id, new_name=body.name
            )
        except DuplicateCollectionName:
            raise AppError(409, "collection_name_taken", "A collection with that name already exists.")
    if body.description is not None:
        col.description = body.description # type: ignore
        await db.flush()
    await db.commit()
    return _out(col)


@router.delete("/{collection_id}", status_code=204)
async def delete_collection(
    collection_id: str,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    deleted = await collections_repo.delete_collection(
        db, user_id=user.id, collection_id=collection_id
    )
    if not deleted:
        raise AppError(404, "not_found", "Collection not found.")
    await db.commit()


@router.post("/{collection_id}/recipes/{recipe_id}", status_code=204)
async def add_recipe(
    collection_id: str,
    recipe_id: str,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    try:
        await collections_repo.add_recipe_to_collection(
            db, user_id=user.id, recipe_id=recipe_id, collection_id=collection_id
        )
    except CrossUserError:
        raise AppError(404, "not_found", "Recipe or collection not found.")
    await db.commit()


@router.delete("/{collection_id}/recipes/{recipe_id}", status_code=204)
async def remove_recipe(
    collection_id: str,
    recipe_id: str,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    removed = await collections_repo.remove_recipe_from_collection(
        db, user_id=user.id, recipe_id=recipe_id, collection_id=collection_id
    )
    if not removed:
        raise AppError(404, "not_found", "Recipe or collection not found.")
    await db.commit()
