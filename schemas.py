from pydantic import BaseModel


class RecipeData(BaseModel):
    title: str | None = None
    ingredients: list[str] | None = None
    instructions: str | None = None
    image: str | None = None
    prep_time: int | None = None
    cook_time: int | None = None
    total_time: int | None = None
    yields: str | None = None
    host: str | None = None
    url: str
    cuisine: str | None = None
    category: str | None = None
    language: str | None = None
    method: str | None = None
    warnings: list[str] = []
