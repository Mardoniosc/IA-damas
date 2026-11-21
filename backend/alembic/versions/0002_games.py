"""Games and game positions (G13).

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "games",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column("event", sa.String(200)),
        sa.Column("white", sa.String(100), nullable=False),
        sa.Column("black", sa.String(100), nullable=False),
        sa.Column("result", sa.String(10), nullable=False),
        sa.Column("variant", sa.String(40), nullable=False),
        sa.Column("start_fen", sa.String(400), nullable=False),
        sa.Column("plies", sa.Integer(), nullable=False),
        sa.Column("termination", sa.String(200)),
        sa.Column("pdn", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_games_white", "games", ["white"])
    op.create_index("ix_games_black", "games", ["black"])
    op.create_table(
        "game_positions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id"), nullable=False),
        sa.Column("ply", sa.Integer(), nullable=False),
        sa.Column("position_id", sa.Integer(), sa.ForeignKey("positions.id"), nullable=False),
        sa.Column("move", sa.String(80)),
        sa.Column("label", sa.String(20)),
        sa.Column("regret", sa.Float()),
        sa.UniqueConstraint("game_id", "ply", name="uq_game_positions_game_ply"),
    )
    op.create_index("ix_game_positions_game_id", "game_positions", ["game_id"])
    op.create_index("ix_game_positions_position_id", "game_positions", ["position_id"])


def downgrade() -> None:
    op.drop_table("game_positions")
    op.drop_table("games")
