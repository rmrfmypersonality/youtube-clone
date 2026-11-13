import argparse
import asyncio
import re
import secrets

from sqlalchemy import select

from app.core.database import SessionLocal, engine
from app.core.security import hash_password
from app.models import Channel, Role, User
from app.schemas.auth import USERNAME_RE


async def run(email: str, username: str, password: str | None, role: Role) -> None:
    async with SessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if user is not None:
            user.role = role
            await session.commit()
            print(f"Пользователь {email} уже существует, роль: {role.value}")
        else:
            generated = password is None
            password = password or secrets.token_urlsafe(12)
            session.add(
                User(
                    email=email,
                    username=username,
                    password_hash=hash_password(password),
                    role=role,
                    channel=Channel(handle=username, name=username),
                )
            )
            await session.commit()
            print(f"Создан {role.value}: {email} / {password}" + (" (пароль сгенерирован)" if generated else ""))
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password")
    parser.add_argument("--role", choices=[r.value for r in Role], default=Role.admin.value)
    args = parser.parse_args()
    if not re.match(USERNAME_RE, args.username):
        parser.error("username: 3-30 символов, латиница, цифры, _")
    asyncio.run(run(args.email, args.username, args.password, Role(args.role)))


if __name__ == "__main__":
    main()