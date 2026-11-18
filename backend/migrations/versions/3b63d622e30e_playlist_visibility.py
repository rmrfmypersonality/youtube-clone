"""playlist visibility

Revision ID: 3b63d622e30e
Revises: f78b786f651d
Create Date: 2026-11-17 22:30:08.756806

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3b63d622e30e'
down_revision: Union[str, Sequence[str], None] = 'f78b786f651d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_playlists_watch_later_private"), "playlists", type_="check")
    op.add_column(
        "playlists",
        sa.Column("visibility", sa.String(length=16), server_default="private", nullable=False),
    )
    op.execute(
        "UPDATE playlists SET visibility = CASE WHEN is_public THEN 'public' ELSE 'private' END"
    )
    op.create_check_constraint(
        op.f("ck_playlists_visibility_valid"),
        "playlists",
        "visibility IN ('public', 'unlisted', 'private')",
    )
    op.create_check_constraint(
        op.f("ck_playlists_watch_later_private"),
        "playlists",
        "kind <> 'watch_later' OR visibility = 'private'",
    )
    op.drop_column("playlists", "is_public")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_playlists_watch_later_private"), "playlists", type_="check")
    op.drop_constraint(op.f("ck_playlists_visibility_valid"), "playlists", type_="check")
    op.add_column(
        "playlists",
        sa.Column("is_public", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.execute("UPDATE playlists SET is_public = (visibility = 'public')")
    op.create_check_constraint(
        op.f("ck_playlists_watch_later_private"),
        "playlists",
        "kind <> 'watch_later' OR is_public IS FALSE",
    )
    op.drop_column("playlists", "visibility")
