from fastapi import APIRouter

from app.core.deps import SessionDep
from app.repositories.categories import CategoryRepository
from app.schemas.categories import CategoryOut

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
async def list_categories(session: SessionDep):
    return await CategoryRepository(session).list_all()