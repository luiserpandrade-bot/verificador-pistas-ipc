"""Resolución de la identidad del usuario en una sesión MCP.

Artículo VI.4, al pie de la letra:

- Si el transporte aporta un **token verificado**, la tool DEBE usar la identidad de ese
  token: el mismo JWT que usa REST, decodificado con la misma función
  (`app.utils.seguridad.decodificar_token`).
- Si el transporte es `stdio` y no hay forma de propagar identidad real, se usa un
  usuario demo. Es una **simplificación consciente** y queda documentada aquí de forma
  explícita, nunca como un olvido silencioso.
- El usuario demo es solo el fallback legítimo cuando no hay ningún token disponible.
  Nunca sustituye a un token válido.

Artículo IV.4: el `usuario_id` no se acepta jamás como argumento de una tool. Las tools
piden la identidad a este módulo y a ningún otro sitio.

Artículo VII.3: este módulo está en la lista `omit` de cobertura por ser infraestructura,
pero sus reglas de identidad sí tienen tests propios en `tests/mcp/test_identidad.py`.
"""

from dataclasses import dataclass
from typing import Any

from app.config import obtener_configuracion
from app.repositories.usuarios import UsuariosRepo, usuarios_repo
from app.utils.seguridad import TokenInvalido, decodificar_token

#: Email del usuario demo usado como fallback cuando el transporte no propaga identidad.
EMAIL_USUARIO_DEMO = "demo@example.com"


class IdentidadNoDisponible(Exception):
    """No se pudo determinar ningún usuario para la sesión MCP."""


@dataclass(frozen=True)
class Identidad:
    """Usuario resuelto para una sesión MCP, y cómo se resolvió.

    `es_demo` existe para que la respuesta de la tool pueda decir la verdad sobre qué
    identidad se usó, en vez de hacer pasar al usuario demo por un usuario autenticado.
    """

    usuario_id: int
    email: str
    es_demo: bool


def _usuario_demo(repo: UsuariosRepo) -> Identidad:
    """Devuelve (creándolo si hace falta) el usuario demo del fallback documentado."""
    usuario = repo.obtener_por_email(EMAIL_USUARIO_DEMO)
    if usuario is None:
        # Contraseña imposible de usar: el demo no es una cuenta con la que autenticarse
        # por REST, solo un propietario de datos para la sesión `stdio`.
        usuario = repo.crear(EMAIL_USUARIO_DEMO, "!sin-acceso-por-contrasena!")
    return Identidad(usuario_id=usuario.id, email=usuario.email, es_demo=True)


def resolver_identidad(
    token: str | None = None,
    repo: UsuariosRepo = usuarios_repo,
    clave_secreta: str | None = None,
) -> Identidad:
    """Resuelve qué usuario opera en esta sesión MCP.

    Con token verificable, ese usuario. Sin token, el usuario demo. Con un token que no
    se puede verificar, error: un token inválido **no** cae al fallback, porque eso
    convertiría una credencial rechazada en acceso concedido.
    """
    if token is None:
        return _usuario_demo(repo)

    secreto = clave_secreta or obtener_configuracion().secret_key
    try:
        sujeto = decodificar_token(token, secreto)
    except TokenInvalido as error:
        raise IdentidadNoDisponible("el token de la sesión MCP no es válido") from error

    try:
        usuario_id = int(sujeto)
    except ValueError as error:
        raise IdentidadNoDisponible("el token no identifica a un usuario") from error

    usuario: Any = repo.obtener_por_id(usuario_id)
    if usuario is None:
        raise IdentidadNoDisponible("el usuario del token ya no existe")

    return Identidad(usuario_id=usuario.id, email=usuario.email, es_demo=False)
