"""Modelo de persistencia del Usuario.

Atributos exactamente los que declara `data-model.md`: `email` único y el hash de la
contraseña. No hay marcas de tiempo ni columnas derivadas, porque la especificación no
las declara (decisión R-011).

Artículo IV.1: la columna guarda el hash bcrypt, nunca la contraseña en texto plano.
El schema de salida `UsuarioOut` no expone este campo.
"""

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:  # pragma: no cover - solo para anotaciones
    from app.models.pista import Pista


class Usuario(Base):
    """Diseñador que registra pistas. Su email lo identifica de forma única."""

    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # La clave ajena vive en `pistas.usuario_id` (Artículo III.3); aquí solo el lado
    # inverso de la relación.
    pistas: Mapped[list["Pista"]] = relationship(
        back_populates="usuario",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover - ayuda de depuración
        return f"Usuario(id={self.id!r}, email={self.email!r})"
