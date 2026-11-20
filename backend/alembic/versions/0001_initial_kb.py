"""Initial knowledge-base schema (G11).

Revision ID: 0001
Revises:
Create Date: 2026-11-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "positions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("variant", sa.String(40), nullable=False),
        sa.Column("ruleset_id", sa.String(60), nullable=False),
        sa.Column("dsa", sa.String(64), nullable=False),
        sa.Column("canonical_dsa", sa.String(64), nullable=False),
        sa.Column("fen", sa.String(400), nullable=False),
        sa.Column("zobrist", sa.BigInteger(), nullable=False),
        sa.Column("side_to_move", sa.String(1), nullable=False),
        sa.Column("white_men", sa.Integer(), nullable=False),
        sa.Column("white_kings", sa.Integer(), nullable=False),
        sa.Column("black_men", sa.Integer(), nullable=False),
        sa.Column("black_kings", sa.Integer(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.UniqueConstraint("variant", "dsa", name="uq_positions_variant_dsa"),
    )
    op.create_index("ix_positions_canonical", "positions", ["variant", "canonical_dsa"])
    op.create_index("ix_positions_zobrist", "positions", ["zobrist"])

    op.create_table(
        "engine_analyses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("position_id", sa.Integer(), sa.ForeignKey("positions.id"), nullable=False),
        sa.Column("run_id", sa.String(40), nullable=False),
        sa.Column("engine_id", sa.String(60), nullable=False),
        sa.Column("engine_name", sa.String(60)),
        sa.Column("engine_version", sa.String(30)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("best_move", sa.String(80)),
        sa.Column("score_text", sa.String(20)),
        sa.Column("score_value", sa.Float()),
        sa.Column("score_unit", sa.String(40)),
        sa.Column("score_kind", sa.String(20)),
        sa.Column("depth", sa.Integer()),
        sa.Column("nodes", sa.BigInteger()),
        sa.Column("elapsed_s", sa.Float()),
        sa.Column("limit", sa.JSON(), nullable=False),
        sa.Column("config_fingerprint", sa.String(32)),
        sa.Column("created_at", TZ, nullable=False),
    )
    for col in ("position_id", "run_id", "engine_id"):
        op.create_index(f"ix_engine_analyses_{col}", "engine_analyses", [col])

    op.create_table(
        "consensus_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("position_id", sa.Integer(), sa.ForeignKey("positions.id"), nullable=False),
        sa.Column("run_id", sa.String(40), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("classification", sa.String(30), nullable=False),
        sa.Column("proof_gap", sa.Boolean(), nullable=False),
        sa.Column("unanimous", sa.Boolean(), nullable=False),
        sa.Column("agreement_ratio", sa.Float()),
        sa.Column("engines", sa.JSON(), nullable=False),
        sa.Column("limit", sa.JSON(), nullable=False),
        sa.Column("trajectory", sa.JSON()),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
    )
    for col in ("position_id", "run_id", "classification"):
        op.create_index(f"ix_consensus_records_{col}", "consensus_records", [col])

    op.create_table(
        "tactical_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("position_id", sa.Integer(), sa.ForeignKey("positions.id"), nullable=False),
        sa.Column("critical", sa.Boolean(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("shot_move", sa.String(80)),
        sa.Column("shot_gain_men", sa.Float()),
        sa.Column("shot_sacrifice", sa.Boolean()),
        sa.Column("thresholds", sa.JSON(), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
    )
    op.create_index("ix_tactical_records_position_id", "tactical_records", ["position_id"])
    op.create_index("ix_tactical_records_critical", "tactical_records", ["critical"])

    op.create_table(
        "decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("position_id", sa.Integer(), sa.ForeignKey("positions.id"), nullable=False),
        sa.Column("move", sa.String(80)),
        sa.Column("confidence", sa.String(10), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("engines", sa.JSON(), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
    )
    op.create_index("ix_decisions_position_id", "decisions", ["position_id"])
    op.create_index("ix_decisions_confidence", "decisions", ["confidence"])

    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("position_id", sa.Integer(), sa.ForeignKey("positions.id"), nullable=False),
        sa.Column("tag", sa.String(60), nullable=False),
        sa.Column("source", sa.String(60), nullable=False),
        sa.Column("note", sa.String(400)),
        sa.Column("created_at", TZ, nullable=False),
        sa.UniqueConstraint("position_id", "tag", "source", name="uq_tags_position_tag_source"),
    )
    op.create_index("ix_tags_position_id", "tags", ["position_id"])
    op.create_index("ix_tags_tag", "tags", ["tag"])


def downgrade() -> None:
    for table in ("tags", "decisions", "tactical_records", "consensus_records", "engine_analyses", "positions"):
        op.drop_table(table)
