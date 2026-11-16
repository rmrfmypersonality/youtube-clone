from pydantic import BaseModel


class CategoryOut(BaseModel):
    id: int
    slug: str
    name: str