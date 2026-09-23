"""Repositorio de pistas: única capa autorizada a tocar la base de datos.

Artículo I.3: solo operaciones de persistencia. Ninguna comparación de anchos, ningún
umbral de la norma y ninguna decisión sobre pertenencia: eso es del service.

Artículo III.3: `listar_por_usuario` filtra **siempre** por `usuario_id`. El único
método que no filtra es `obtener_por_id`, y es deliberado: el service necesita ver la
pista para distinguir "no existe" (404) de "existe pero es de otro" (403), que es lo
que exige el Artículo V.1. La decisión la toma el service, nunca esta capa.

Operaciones completas: `guardar` (T014) y el listado, lectura, actualización y borrado
de US3 (T032).
"""

from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import obtener_fabrica_de_sesiones
from app.models.pista import Pista


class PistasRepo(Protocol):
    """Contrato que debe cumplir cualquier repositorio de pistas, real o falso."""

    def guardar(self, usuario_id: int, datos: dict[str, Any]) -> Pista: ...

    def listar_por_usuario(
        self, usuario_id: int, skip: int = 0, limit: int = 20
    ) -> list[Pista]: ...

    def obtener_por_id(self, pista_id: int) -> Pista | None: ...

    def actualizar(self, pista_id: int, datos: dict[str, Any]) -> Pista: ...

    def eliminar(self, pista_id: int) -> None: ...


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

    def listar_por_usuario(
        self, usuario_id: int, skip: int = 0, limit: int = 20
    ) -> list[Pista]:
        """Pistas de ese usuario, ordenadas por identificador y paginadas.

        El filtro por `usuario_id` no es opcional ni parametrizable: está en la consulta
        (Artículo III.3). No existe ninguna operación que devuelva pistas de varios dueños.
        """
        consulta = (
            select(Pista)
            .where(Pista.usuario_id == usuario_id)
            .order_by(Pista.id)
            .offset(skip)
            .limit(limit)
        )
        return list(self._sesion.scalars(consulta))

    def obtener_por_id(self, pista_id: int) -> Pista | None:
        """Pista con ese identificador, sin filtrar por usuario.

        Deliberado: el service necesita ver la pista para distinguir 404 ("no existe") de
        403 ("existe pero es de otro"), como exige el Artículo V.1. La decisión de
        pertenencia la toma el service, nunca esta capa.
        """
        return self._sesion.get(Pista, pista_id)

    def actualizar(self, pista_id: int, datos: dict[str, Any]) -> Pista:
        """Aplica `datos` sobre la pista y devuelve el resultado ya persistido."""
        pista = self._sesion.get(Pista, pista_id)
        if pista is None:
            raise KeyError(pista_id)
        for campo, valor in datos.items():
            setattr(pista, campo, valor)
        self._sesion.commit()
        self._sesion.refresh(pista)
        return pista

    def eliminar(self, pista_id: int) -> None:
        """Borra la pista de forma definitiva."""
        pista = self._sesion.get(Pista, pista_id)
        if pista is None:
            raise KeyError(pista_id)
        self._sesion.delete(pista)
        self._sesion.commit()


class RepositorioPistasPorDefecto:
    """Repositorio que abre su propia sesión en cada operación.

    Valor por defecto del parámetro `repo` de los services (Artículo II.3), para que
    funcionen fuera de una petición HTTP, por ejemplo desde el servidor MCP.
    """

    def guardar(self, usuario_id: int, datos: dict[str, Any]) -> Pista:
        with obtener_fabrica_de_sesiones()() as sesion:
            return RepositorioPistas(sesion).guardar(usuario_id, datos)

    def listar_por_usuario(
        self, usuario_id: int, skip: int = 0, limit: int = 20
    ) -> list[Pista]:
        with obtener_fabrica_de_sesiones()() as sesion:
            return RepositorioPistas(sesion).listar_por_usuario(usuario_id, skip, limit)

    def obtener_por_id(self, pista_id: int) -> Pista | None:
        with obtener_fabrica_de_sesiones()() as sesion:
            return RepositorioPistas(sesion).obtener_por_id(pista_id)

    def actualizar(self, pista_id: int, datos: dict[str, Any]) -> Pista:
        with obtener_fabrica_de_sesiones()() as sesion:
            return RepositorioPistas(sesion).actualizar(pista_id, datos)

    def eliminar(self, pista_id: int) -> None:
        with obtener_fabrica_de_sesiones()() as sesion:
            RepositorioPistas(sesion).eliminar(pista_id)


pistas_repo: PistasRepo = RepositorioPistasPorDefecto()
