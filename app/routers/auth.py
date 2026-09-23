"""Rutas de registro y obtención de token.

Artículo I.1: el router recibe la petición, delega en `services/auth.py` y traduce el
resultado o la excepción de dominio a una respuesta HTTP. No valida ninguna regla de
negocio por su cuenta: que un email esté tomado lo decide el service.
Artículo V.1: `POST /auth/registro` devuelve 201, el email repetido es 400, las
credenciales inválidas son 401 y un cuerpo mal formado es 422 (lo produce Pydantic).
Artículo IV.2: el token es OAuth2 password flow + JWT.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.config import Configuracion
from app.dependencies import get_config, get_usuarios_repo
from app.repositories.usuarios import UsuariosRepo
from app.schemas.usuario import Token, UsuarioCreate, UsuarioOut
from app.services import auth as servicio_auth
from app.services.errores import CredencialesInvalidasError, EmailYaRegistradoError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/registro", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def registrar(
    datos: UsuarioCreate,
    repo: Annotated[UsuariosRepo, Depends(get_usuarios_repo)],
) -> UsuarioOut:
    """Registra un usuario nuevo."""
    try:
        usuario = servicio_auth.registrar_usuario(str(datos.email), datos.password, repo=repo)
    except EmailYaRegistradoError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya está registrado",
        ) from error
    return UsuarioOut.model_validate(usuario)


@router.post("/token", response_model=Token)
def obtener_token(
    formulario: Annotated[OAuth2PasswordRequestForm, Depends()],
    repo: Annotated[UsuariosRepo, Depends(get_usuarios_repo)],
    configuracion: Annotated[Configuracion, Depends(get_config)],
) -> Token:
    """Emite un token de acceso para unas credenciales válidas.

    El formulario OAuth2 llama `username` al campo de identidad; aquí ese campo es el
    email del diseñador.
    """
    try:
        usuario = servicio_auth.autenticar_usuario(
            formulario.username, formulario.password, repo=repo
        )
    except CredencialesInvalidasError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    token = servicio_auth.emitir_token(
        usuario,
        configuracion.secret_key,
        configuracion.access_token_expire_minutes,
    )
    return Token(access_token=token)
