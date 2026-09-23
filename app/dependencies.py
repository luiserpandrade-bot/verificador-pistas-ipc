"""Dependencias de FastAPI: sesión, repositorios e identidad del usuario.

Artículo IV.4 (innegociable): `get_current_user` deriva el usuario **solo** del JWT
decodificado. Aquí no se lee ningún `usuario_id` de la ruta, del cuerpo ni de un query
param, y ninguna otra dependencia lo ofrece.

Artículo VII.5: estas cuatro dependencias son justo las que los tests de API sustituyen
con `app.dependency_overrides`, por eso viven en un módulo propio y no dentro de los
routers.
"""

from collections.abc import Iterator
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import Configuracion, obtener_configuracion
from app.database import sesiones
from app.repositories.pistas import PistasRepo, RepositorioPistas
from app.repositories.usuarios import RepositorioUsuarios, UsuariosRepo
from app.utils.seguridad import TokenInvalido, decodificar_token

esquema_oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/token")

CREDENCIALES_INVALIDAS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="No autenticado",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_db() -> Iterator[Session]:
    """Cede una sesión de base de datos por petición."""
    yield from sesiones()


def get_usuarios_repo(sesion: Annotated[Session, Depends(get_db)]) -> UsuariosRepo:
    """Repositorio de usuarios ligado a la sesión de esta petición."""
    return RepositorioUsuarios(sesion)


def get_pistas_repo(sesion: Annotated[Session, Depends(get_db)]) -> PistasRepo:
    """Repositorio de pistas ligado a la sesión de esta petición."""
    return RepositorioPistas(sesion)


def get_config() -> Configuracion:
    """Configuración de la aplicación."""
    return obtener_configuracion()


def get_current_user(
    token: Annotated[str, Depends(esquema_oauth2)],
    repo: Annotated[UsuariosRepo, Depends(get_usuarios_repo)],
    configuracion: Annotated[Configuracion, Depends(get_config)],
) -> Any:
    """Devuelve el usuario autenticado a partir del token, o 401.

    El identificador sale del `sub` del JWT. Si el token es inválido, está expirado o
    apunta a un usuario que ya no existe, la petición es 401: nunca se cae a un usuario
    por defecto ni se acepta identidad por otra vía (Artículo IV.4).
    """
    try:
        sujeto = decodificar_token(token, configuracion.secret_key)
    except TokenInvalido as error:
        raise CREDENCIALES_INVALIDAS from error

    try:
        usuario_id = int(sujeto)
    except ValueError as error:
        raise CREDENCIALES_INVALIDAS from error

    usuario = repo.obtener_por_id(usuario_id)
    if usuario is None:
        raise CREDENCIALES_INVALIDAS
    return usuario
