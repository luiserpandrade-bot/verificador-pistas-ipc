"""Tests unitarios del service de autenticación con repositorio falso.

Artículo VII.2: el repositorio falso se inyecta por parámetro; `unittest.mock` está
prohibido para esto y no aparece en este archivo.
"""

import ast
import inspect as inspeccion

import pytest

from app.services.auth import (
    autenticar_usuario,
    emitir_token,
    registrar_usuario,
)
from app.services.errores import CredencialesInvalidasError, EmailYaRegistradoError
from app.utils.seguridad import decodificar_token
from tests.fakes import RepositorioUsuariosFalso

CLAVE = "clave-de-prueba"


def test_registrar_usuario_guarda_con_contrasena_hasheada(
    repo_usuarios_falso: RepositorioUsuariosFalso,
) -> None:
    usuario = registrar_usuario("nuevo@example.com", "secreto", repo=repo_usuarios_falso)

    assert usuario.email == "nuevo@example.com"
    assert usuario.hashed_password != "secreto"
    assert usuario.hashed_password.startswith("$2b$")


def test_registrar_usuario_con_email_repetido_se_rechaza(
    repo_usuarios_falso: RepositorioUsuariosFalso,
) -> None:
    registrar_usuario("repetido@example.com", "secreto", repo=repo_usuarios_falso)

    with pytest.raises(EmailYaRegistradoError):
        registrar_usuario("repetido@example.com", "otra", repo=repo_usuarios_falso)

    assert len(repo_usuarios_falso.usuarios) == 1


def test_autenticar_con_credenciales_correctas_devuelve_el_usuario(
    repo_usuarios_falso: RepositorioUsuariosFalso,
) -> None:
    creado = registrar_usuario("disenador@example.com", "secreto", repo=repo_usuarios_falso)

    autenticado = autenticar_usuario("disenador@example.com", "secreto", repo=repo_usuarios_falso)

    assert autenticado.id == creado.id


def test_autenticar_con_contrasena_incorrecta_se_rechaza(
    repo_usuarios_falso: RepositorioUsuariosFalso,
) -> None:
    registrar_usuario("disenador@example.com", "secreto", repo=repo_usuarios_falso)

    with pytest.raises(CredencialesInvalidasError):
        autenticar_usuario("disenador@example.com", "incorrecta", repo=repo_usuarios_falso)


def test_autenticar_email_inexistente_da_el_mismo_error_que_contrasena_mala(
    repo_usuarios_falso: RepositorioUsuariosFalso,
) -> None:
    """No se distingue el caso para no permitir enumerar emails registrados."""
    registrar_usuario("existe@example.com", "secreto", repo=repo_usuarios_falso)

    with pytest.raises(CredencialesInvalidasError) as inexistente:
        autenticar_usuario("nadie@example.com", "secreto", repo=repo_usuarios_falso)
    with pytest.raises(CredencialesInvalidasError) as mala:
        autenticar_usuario("existe@example.com", "mala", repo=repo_usuarios_falso)

    assert str(inexistente.value) == str(mala.value)


def test_emitir_token_produce_un_jwt_del_usuario(
    repo_usuarios_falso: RepositorioUsuariosFalso,
) -> None:
    usuario = registrar_usuario("disenador@example.com", "secreto", repo=repo_usuarios_falso)

    token = emitir_token(usuario, CLAVE, minutos_de_expiracion=30)

    assert decodificar_token(token, CLAVE) == str(usuario.id)


def test_el_repositorio_es_un_parametro_con_valor_por_defecto() -> None:
    """Artículo II.3: es lo que hace innecesario `unittest.mock`."""
    for funcion in (registrar_usuario, autenticar_usuario):
        parametro = inspeccion.signature(funcion).parameters["repo"]
        assert parametro.default is not inspeccion.Parameter.empty


def test_el_service_no_conoce_la_persistencia_ni_el_framework_web() -> None:
    """Artículos I.2 y R-009: ni SQLAlchemy ni FastAPI en la capa de servicios."""
    import app.services.auth as modulo

    arbol = ast.parse(inspeccion.getsource(modulo))
    importados: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            importados.update(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            importados.add(nodo.module)

    for prohibido in ("sqlalchemy", "fastapi", "app.database", "app.models"):
        assert not any(nombre.startswith(prohibido) for nombre in importados), (
            f"services/auth.py no debe importar {prohibido}: {importados}"
        )


def test_no_se_usa_unittest_mock_en_este_archivo() -> None:
    """Artículo VII.2."""
    arbol = ast.parse(open(__file__, encoding="utf-8").read())
    importados = {
        nodo.module
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.ImportFrom) and nodo.module
    }

    assert not any(nombre.startswith("unittest") for nombre in importados)
