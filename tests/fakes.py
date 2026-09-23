"""Repositorios falsos para los tests unitarios de `services/`.

El Artículo VII.2 **prohíbe** `unittest.mock` para sustituir un repositorio: el diseño
con DIP del Artículo II.3 (el service recibe el repositorio por parámetro, con valor
por defecto) ya lo hace innecesario. Estas clases cumplen el mismo contrato que los
repositorios reales, guardando en memoria.

Se comportan como el repositorio real en lo que importa para las reglas de negocio:
asignan identificadores, y **filtran siempre por `usuario_id`** (Artículo III.3), de
modo que un test de R4 que pase con el falso también pasaría contra la base de datos.
"""

from dataclasses import dataclass, field, replace
from typing import Any


@dataclass
class UsuarioFalso:
    """Equivalente en memoria de `app.models.usuario.Usuario`."""

    id: int
    email: str
    hashed_password: str


@dataclass
class PistaFalsa:
    """Equivalente en memoria de `app.models.pista.Pista`."""

    id: int
    usuario_id: int
    nombre_red: str
    proyecto: str
    corriente_a: float
    espesor_oz: float
    capa: str
    delta_t_c: float
    ancho_mm: float


@dataclass
class RepositorioUsuariosFalso:
    """Repositorio de usuarios en memoria."""

    usuarios: dict[int, UsuarioFalso] = field(default_factory=dict)
    _siguiente_id: int = 1

    def crear(self, email: str, hashed_password: str) -> UsuarioFalso:
        usuario = UsuarioFalso(
            id=self._siguiente_id, email=email, hashed_password=hashed_password
        )
        self.usuarios[usuario.id] = usuario
        self._siguiente_id += 1
        return usuario

    def obtener_por_email(self, email: str) -> UsuarioFalso | None:
        return next((u for u in self.usuarios.values() if u.email == email), None)

    def obtener_por_id(self, usuario_id: int) -> UsuarioFalso | None:
        return self.usuarios.get(usuario_id)


@dataclass
class RepositorioPistasFalso:
    """Repositorio de pistas en memoria.

    `escrituras` lleva la cuenta de las operaciones de escritura efectuadas. Los tests
    de R1, R2 y R5 la usan para comprobar que una operación rechazada **no** llegó a
    persistir nada, que es la diferencia entre rechazar y guardar mal.
    """

    pistas: dict[int, PistaFalsa] = field(default_factory=dict)
    escrituras: list[str] = field(default_factory=list)
    _siguiente_id: int = 1

    def guardar(self, usuario_id: int, datos: dict[str, Any]) -> PistaFalsa:
        pista = PistaFalsa(id=self._siguiente_id, usuario_id=usuario_id, **datos)
        self.pistas[pista.id] = pista
        self._siguiente_id += 1
        self.escrituras.append("guardar")
        return pista

    def listar_por_usuario(
        self, usuario_id: int, skip: int = 0, limit: int = 20
    ) -> list[PistaFalsa]:
        propias = [p for p in self.pistas.values() if p.usuario_id == usuario_id]
        propias.sort(key=lambda p: p.id)
        return propias[skip : skip + limit]

    def obtener_por_id(self, pista_id: int) -> PistaFalsa | None:
        """Devuelve la pista sin filtrar por usuario: la pertenencia la decide el service.

        Es deliberado. Para distinguir 403 (existe pero es ajena) de 404 (no existe),
        el service necesita ver la pista antes de decidir (Artículo IV.4).
        """
        return self.pistas.get(pista_id)

    def actualizar(self, pista_id: int, datos: dict[str, Any]) -> PistaFalsa:
        actual = self.pistas[pista_id]
        actualizada = replace(actual, **datos)
        self.pistas[pista_id] = actualizada
        self.escrituras.append("actualizar")
        return actualizada

    def eliminar(self, pista_id: int) -> None:
        del self.pistas[pista_id]
        self.escrituras.append("eliminar")
