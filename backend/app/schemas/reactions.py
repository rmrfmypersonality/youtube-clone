from typing import Literal

from pydantic import BaseModel


class ReactionIn(BaseModel):
    value: Literal[1, -1, 0]  # 0 = снять реакцию


class ReactionOut(BaseModel):
    likes_count: int
    my_reaction: int