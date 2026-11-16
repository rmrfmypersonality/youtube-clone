from pydantic import BaseModel, Field


class AccountDelete(BaseModel):
    password: str = Field(min_length=1, max_length=128)