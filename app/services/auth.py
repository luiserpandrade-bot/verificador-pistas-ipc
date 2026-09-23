"""Lógica de negocio de registro y autenticación.

Artículo I.2: este módulo no importa SQLAlchemy ni `Session`. Solo conoce el contrato
`UsuariosRepo`.
Artículo II.3 (innegociable): el repositorio llega **por parámetro con valor por
defecto**, que es lo que permite testear con un repositorio falso sin `unittest.mock`.
Artículo II.1: la validación (`_validar_email_disponible`) está separada de la
orquestación (`registrar_usuario`).
Artículo IV.1: la contraseña se hashea aquí y nunca se devuelve ni se registra.
"""

from typing import Any

from app.repositories.usuarios import UsuariosRepo, usuarios_repo
from app.services.errores import CredencialesInvalidasError, EmailYaRegistradoError
from app.utils.seguridad import crear_token_de_acceso, hashear_contrasena, verificar_contrasena


def _validar_email_disponible(email: str, repo: UsuariosRepo) -> None:
    """Rechaza el registro si el email ya está tomado (FR-001)."""
    if repo.obtener_por_email(email) is not None:
        raise EmailYaRegistradoError(f"el email {email} ya está registrado")


def registrar_usuario(
    email: str,
    contrasena: str,
    repo: UsuariosRepo = usuarios_repo,
) -> Any:
    """Registra un usuario nuevo con su contraseña hasheada y lo devuelve."""
    _validar_email_disponible(email, repo)
    return repo.crear(email, hashear_contrasena(contrasena))


def autenticar_usuario(
    email: str,
    contrasena: str,
    repo: UsuariosRepo = usuarios_repo,
) -> Any:
    """Devuelve el usuario si las credenciales son correctas.

    Lanza el mismo error tanto si el email no existe como si la contraseña no coincide:
    distinguirlos permitiría enumerar qué emails están registrados.
    """
    usuario = repo.obtener_por_email(email)
    if usuario is None or not verificar_contrasena(contrasena, usuario.hashed_password):
        raise CredencialesInvalidasError("email o contraseña incorrectos")
    return usuario


def emitir_token(usuario: Any, clave_secreta: str, minutos_de_expiracion: int) -> str:
    """Emite el JWT de acceso de ese usuario (Artículo IV.2)."""
    return crear_token_de_acceso(
        sujeto=str(usuario.id),
        clave_secreta=clave_secreta,
        minutos_de_expiracion=minutos_de_expiracion,
    )
