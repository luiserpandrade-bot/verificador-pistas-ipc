"""Repositorio de usuarios: única capa autorizada a tocar la base de datos.

Artículo I.3: aquí viven las operaciones de persistencia y **ninguna** regla de
negocio. Decidir si un email duplicado es un error de negocio es cosa del service; lo
único que hace este módulo es guardar, buscar y devolver.

Artículo I.2: el service no debe conocer `Session` ni SQLAlchemy, así que el
repositorio se construye **ligado a una sesión** y sus métodos no la reciben. El
service solo ve el contrato `UsuariosRepo`.

Artículo II.3: `usuarios_repo` es la instancia por defecto que usan los services
(`def registrar_usuario(..., repo=usuarios_repo)`); abre y cierra su propia sesión. En
la API, `get_usuarios_repo` inyecta en su lugar un repositorio ligado a la sesión de la
petición, y en los tests se sustituye por el falso.
"""

from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import obtener_fabrica_de_sesiones
from app.models.usuario import Usuario


class UsuariosRepo(Protocol):
    """Contrato que debe cumplir cualquier repositorio de usuarios, real o falso."""

    def crear(self, email: str, hashed_password: str) -> Usuario: ...

    def obtener_por_email(self, email: str) -> Usuario | None: ...

    def obtener_por_id(self, usuario_id: int) -> Usuario | None: ...


class RepositorioUsuarios:
    """Repositorio ligado a una sesión concreta."""

    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def crear(self, email: str, hashed_password: str) -> Usuario:
        """Persiste un usuario nuevo y lo devuelve con su identificador."""
        usuario = Usuario(email=email, hashed_password=hashed_password)
        self._sesion.add(usuario)
        self._sesion.commit()
        self._sesion.refresh(usuario)
        return usuario

    def obtener_por_email(self, email: str) -> Usuario | None:
        """Devuelve el usuario con ese email, o `None` si no existe."""
        return self._sesion.scalars(select(Usuario).where(Usuario.email == email)).first()

    def obtener_por_id(self, usuario_id: int) -> Usuario | None:
        """Devuelve el usuario con ese identificador, o `None` si no existe."""
        return self._sesion.get(Usuario, usuario_id)


class RepositorioUsuariosPorDefecto:
    """Repositorio que abre su propia sesión en cada operación.

    Es el valor por defecto del parámetro `repo` de los services, para que funcionen
    fuera de una petición HTTP (por ejemplo desde el servidor MCP por `stdio`).
    """

    def _repositorio(self, sesion: Session) -> RepositorioUsuarios:
        return RepositorioUsuarios(sesion)

    def crear(self, email: str, hashed_password: str) -> Usuario:
        with obtener_fabrica_de_sesiones()() as sesion:
            return self._repositorio(sesion).crear(email, hashed_password)

    def obtener_por_email(self, email: str) -> Usuario | None:
        with obtener_fabrica_de_sesiones()() as sesion:
            return self._repositorio(sesion).obtener_por_email(email)

    def obtener_por_id(self, usuario_id: int) -> Usuario | None:
        with obtener_fabrica_de_sesiones()() as sesion:
            return self._repositorio(sesion).obtener_por_id(usuario_id)


usuarios_repo: UsuariosRepo = RepositorioUsuariosPorDefecto()
