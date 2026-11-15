from typing import Annotated

from fastapi import Path, Query

INT_MAX = 2_147_483_647  # иначе asyncpg на огромном id падает 500, а не 422

IdPath = Annotated[int, Path(ge=1, le=INT_MAX)]
CursorQuery = Annotated[int | None, Query(ge=1, le=INT_MAX)]
LimitQuery = Annotated[int, Query(ge=1, le=50)]