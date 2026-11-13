from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

from app.models import Role

USERNAME_RE = r"^[A-Za-z0-9_]{3,30}$"


def _check_email_len(value: str) -> str:
    if len(value) > 254:
        raise ValueError("email слишком длинный")
    return value


Email = Annotated[EmailStr, AfterValidator(_check_email_len)]


class RegisterIn(BaseModel):
    email: Email
    username: str = Field(pattern=USERNAME_RE)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: Email
    password: str = Field(min_length=1, max_length=128)


class ChannelBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    handle: str
    name: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    username: str
    role: Role
    channel: ChannelBrief