"""Migración inicial: tablas usuarios y pistas.

Crea el esquema que declara `data-model.md`: `usuarios` con email único indexado y
`pistas` con `usuario_id` como clave ajena indexada (Artículo III.3). Sin columnas
derivadas ni estado de conformidad (decisión R-011).

Revision ID: 0001
Revises:
Create Date: 2026-09-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_usuarios_email", "usuarios", ["email"], unique=True)

    op.create_table(
        "pistas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("nombre_red", sa.String(length=120), nullable=False),
        sa.Column("proyecto", sa.String(length=120), nullable=False),
        sa.Column("corriente_a", sa.Float(), nullable=False),
        sa.Column("espesor_oz", sa.Float(), nullable=False),
        sa.Column("capa", sa.String(length=16), nullable=False),
        sa.Column("delta_t_c", sa.Float(), nullable=False),
        sa.Column("ancho_mm", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuarios.id"],
            name="fk_pistas_usuario_id_usuarios",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pistas_usuario_id", "pistas", ["usuario_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pistas_usuario_id", table_name="pistas")
    op.drop_table("pistas")
    op.drop_index("ix_usuarios_email", table_name="usuarios")
    op.drop_table("usuarios")
