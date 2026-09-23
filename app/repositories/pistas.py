"""Repositorio de pistas: única capa autorizada a tocar la base de datos.

Artículo I.3: solo operaciones de persistencia. Ninguna comparación de anchos, ningún
umbral de la norma y ninguna decisión sobre pertenencia: eso es del service.

Artículo III.3: `listar_por_usuario` filtra **siempre** por `usuario_id`. El único
método que no filtra es `obtener_por_id`, y es deliberado: el service necesita ver la
pista para distinguir "no existe" (404) de "existe pero es de otro" (403), que es lo
que exige el Artículo V.1. La decisión la toma el service, nunca esta capa.

En esta tarea (T014) se implementa `guardar`, que es lo que necesita US1. Las
operaciones de listado, lectura, actualización y borrado llegan en T032, con US3.
"""

from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.database import obtener_fabrica_de_sesiones
from app.models.pista import Pista


class PistasRepo(Protocol):
    """Contrato que debe cumplir cualquier repositorio de pistas, real o falso."""

    def guardar(self, usuario_id: int, datos: dict[str, Any]) -> Pista: ...


class RepositorioPistas:
    """Repositorio ligado a una sesión concreta."""

    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def guardar(self, usuario_id: int, datos: dict[str, Any]) -> Pista:
        """Persiste una pista nueva asociada a `usuario_id` y la devuelve."""
        pista = Pista(usuario_id=usuario_id, **datos)
        self._sesion.add(pista)
        self._sesion.commit()
        self._sesion.refresh(pista)
        return pista


class RepositorioPistasPorDefecto:
    """Repositorio que abre su propia sesión en cada operación.

    Valor por defecto del parámetro `repo` de los services (Artículo II.3), para que
    funcionen fuera de una petición HTTP, por ejemplo desde el servidor MCP.
    """

    def guardar(self, usuario_id: int, datos: dict[str, Any]) -> Pista:
        with obtener_fabrica_de_sesiones()() as sesion:
            return RepositorioPistas(sesion).guardar(usuario_id, datos)


pistas_repo: PistasRepo = RepositorioPistasPorDefecto()
