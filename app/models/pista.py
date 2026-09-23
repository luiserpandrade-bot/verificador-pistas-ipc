"""Modelo de persistencia de la Pista.

Atributos exactamente los que declara `data-model.md`. No se persiste el ancho mínimo
calculado ni ningún estado de conformidad: al rechazarse por completo una operación
fuera de norma (R1, R2, R5), no existe una pista "no conforme" que almacenar
(decisión R-011).

Artículo III.3: `usuario_id` es clave ajena obligatoria e indexada. Ninguna consulta
de pistas puede omitir el filtro por esta columna; eso lo garantiza el repositorio.

Los rangos de R2 (corriente, ΔT, espesor) NO se validan aquí ni en el schema: son
regla de negocio y se comprueban en `app/services/pistas.py` devolviendo 400.
"""

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.usuario import Usuario


class Pista(Base):
    """Pista de un diseño de PCB, propiedad de un usuario."""

    __tablename__ = "pistas"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    nombre_red: Mapped[str] = mapped_column(String(120), nullable=False)
    proyecto: Mapped[str] = mapped_column(String(120), nullable=False)
    corriente_a: Mapped[float] = mapped_column(Float, nullable=False)
    espesor_oz: Mapped[float] = mapped_column(Float, nullable=False)
    capa: Mapped[str] = mapped_column(String(16), nullable=False)
    delta_t_c: Mapped[float] = mapped_column(Float, nullable=False)
    ancho_mm: Mapped[float] = mapped_column(Float, nullable=False)

    usuario: Mapped[Usuario] = relationship(back_populates="pistas")

    def __repr__(self) -> str:  # pragma: no cover - ayuda de depuración
        return (
            f"Pista(id={self.id!r}, nombre_red={self.nombre_red!r}, "
            f"usuario_id={self.usuario_id!r})"
        )
