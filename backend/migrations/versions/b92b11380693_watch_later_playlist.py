"""watch later playlist

Revision ID: b92b11380693
Revises: 3d98d00dd330
Create Date: 2026-11-17 00:18:01.945136

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b92b11380693'
down_revision: Union[str, Sequence[str], None] = '3d98d00dd330'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "playlists",
        sa.Column("kind", sa.String(length=16), server_default="regular", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_playlists_kind_valid"), "playlists", "kind IN ('regular', 'watch_later')"
    )
    op.create_check_constraint(
        op.f("ck_playlists_watch_later_private"),
        "playlists",
        "kind <> 'watch_later' OR is_public IS FALSE",
    )
    op.create_index(
        "uq_playlists_watch_later",
        "playlists",
        ["owner_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'watch_later'"),
    )
    # Существующим пользователям: у новых плейлист создастся при первом обращении
    op.execute(
        "INSERT INTO playlists (owner_id, title, description, is_public, kind) "
        "SELECT id, 'Смотреть позже', '', false, 'watch_later' FROM users"
    )


def downgrade() -> None:
    op.execute("DELETE FROM playlists WHERE kind = 'watch_later'")  # элементы уйдут каскадом
    op.drop_index("uq_playlists_watch_later", table_name="playlists")
    op.drop_constraint(op.f("ck_playlists_watch_later_private"), "playlists", type_="check")
    op.drop_constraint(op.f("ck_playlists_kind_valid"), "playlists", type_="check")
    op.drop_column("playlists", "kind")
