"""Primitivas de seguridad: hash de contraseñas y firma/verificación de JWT.

Artículo IV.1: las contraseñas se guardan como hash bcrypt vía `passlib[bcrypt]`,
nunca en texto plano y nunca en una respuesta.
Artículo IV.2: los tokens son JWT firmados con HS256 y con expiración finita; el
número de minutos lo decide quien llama (viene de configuración), nunca es infinito.

Funciones puras respecto al estado de la aplicación: no tocan base de datos ni
importan nada de `services/`, `routers/` ni `repositories/` (Artículo I.4).
"""

from datetime import UTC, datetime, timedelta
from typing import Any, Final

from jose import JWTError, jwt
from passlib.context import CryptContext

ALGORITMO: Final = "HS256"

# Versiones fijadas en pyproject.toml: passlib 1.7.4 con bcrypt 4.0.1. Con bcrypt
# 4.1 o superior passlib falla al leer `bcrypt.__about__.__version__`.
_contexto: Final = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenInvalido(Exception):
    """El token no se puede verificar: firma incorrecta, expirado o manipulado."""


def hashear_contrasena(contrasena: str) -> str:
    """Devuelve el hash bcrypt de una contraseña en texto plano."""
    return _contexto.hash(contrasena)


def verificar_contrasena(contrasena: str, hash_almacenado: str) -> bool:
    """Indica si `contrasena` corresponde al hash almacenado."""
    try:
        return _contexto.verify(contrasena, hash_almacenado)
    except ValueError:
        # Hash con formato inválido: se trata como no coincidente, nunca como error
        # que se propague al cliente.
        return False


def crear_token_de_acceso(
    sujeto: str,
    clave_secreta: str,
    minutos_de_expiracion: int,
) -> str:
    """Firma un JWT HS256 cuyo `sub` es `sujeto` y que expira en el plazo indicado.

    `minutos_de_expiracion` debe ser positivo: un token sin expiración está prohibido
    por el Artículo IV.2.
    """
    if minutos_de_expiracion <= 0:
        raise ValueError("la expiración del token debe ser mayor que 0 minutos")

    ahora = datetime.now(UTC)
    contenido: dict[str, Any] = {
        "sub": sujeto,
        "iat": int(ahora.timestamp()),
        "exp": int((ahora + timedelta(minutes=minutos_de_expiracion)).timestamp()),
    }
    return jwt.encode(contenido, clave_secreta, algorithm=ALGORITMO)


def decodificar_token(token: str, clave_secreta: str) -> str:
    """Devuelve el `sub` de un token válido; lanza `TokenInvalido` en cualquier otro caso."""
    try:
        contenido = jwt.decode(token, clave_secreta, algorithms=[ALGORITMO])
    except JWTError as error:
        raise TokenInvalido(str(error)) from error

    sujeto = contenido.get("sub")
    if not sujeto:
        raise TokenInvalido("el token no identifica a ningún sujeto")
    return str(sujeto)
