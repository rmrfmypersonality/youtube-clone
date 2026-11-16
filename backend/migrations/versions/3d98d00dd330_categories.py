"""categories

Revision ID: 3d98d00dd330
Revises: daa74214ac4c
Create Date: 2026-11-16 23:32:12.987263

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

CATEGORIES = [
    ("music", "Музыка"),
    ("gaming", "Игры"),
    ("news", "Новости"),
    ("film", "Кино и ТВ"),
    ("sports", "Спорт"),
    ("education", "Образование"),
    ("science", "Наука и техника"),
    ("travel", "Путешествия"),
    ("entertainment", "Развлечения"),
    ("other", "Другое"),
]

# revision identifiers, used by Alembic.
revision: str = '3d98d00dd330'
down_revision: Union[str, Sequence[str], None] = 'daa74214ac4c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    categories = op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
        sa.UniqueConstraint("slug", name=op.f("uq_categories_slug")),
    )
    op.bulk_insert(
        categories,
        [{"slug": s, "name": n, "sort_order": i} for i, (s, n) in enumerate(CATEGORIES)],
    )

    op.add_column("videos", sa.Column("category_id", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE videos SET category_id = (SELECT id FROM categories WHERE slug = 'other')"
    )
    op.alter_column("videos", "category_id", nullable=False)
    op.create_foreign_key(
        op.f("fk_videos_category_id_categories"), "videos", "categories", ["category_id"], ["id"]
    )
    op.create_index(op.f("ix_videos_category_id"), "videos", ["category_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_videos_category_id"), table_name="videos")
    op.drop_constraint(op.f("fk_videos_category_id_categories"), "videos", type_="foreignkey")
    op.drop_column("videos", "category_id")
    op.drop_table("categories")
