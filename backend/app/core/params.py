from typing import Annotated

from fastapi import Path, Query, HTTPException

INT_MAX = 2_147_483_647  # иначе asyncpg на огромном id падает 500, а не 422

IdPath = Annotated[int, Path(ge=1, le=INT_MAX)]
CursorQuery = Annotated[int | None, Query(ge=1, le=INT_MAX)]
LimitQuery = Annotated[int, Query(ge=1, le=50)]

# Курсор комментариев: "id" для сортировки new или "лайки_id" для popular
CommentCursorQuery = Annotated[
    str | None, Query(pattern=r"^[0-9]{1,10}(_[0-9]{1,10})?$", max_length=21)
]


def parse_comment_cursor(sort: str, raw: str | None) -> tuple[int | None, int] | None:
    """Возвращает (лайки, id); лайки = None для сортировки new."""
    if raw is None:
        return None
    parts = [int(p) for p in raw.split("_")]
    expected = 2 if sort == "popular" else 1
    if len(parts) != expected or any(p > INT_MAX for p in parts) or parts[-1] < 1:
        raise HTTPException(status_code=422, detail="Некорректный курсор")
    return (parts[0], parts[1]) if expected == 2 else (None, parts[0])