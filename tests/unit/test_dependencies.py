"""Tests de las dependencias de FastAPI, sobre todo del Artículo IV.4.

La identidad debe salir del token y de ningún otro sitio. Estos tests fijan ese
comportamiento antes de que exista un router que pudiera saltárselo.
"""

import ast
import inspect as inspeccion

import pytest
from fastapi import HTTPException

from app.config import Configuracion
from app.dependencies import (
    get_current_user,
    get_db,
    get_pistas_repo,
    get_usuarios_repo,
)
from app.repositories.pistas import RepositorioPistas
from app.repositories.usuarios import RepositorioUsuarios
from app.utils.seguridad import crear_token_de_acceso
from tests.fakes import RepositorioUsuariosFalso

CLAVE = "clave-de-prueba"


@pytest.fixture
def configuracion() -> Configuracion:
    return Configuracion(  # type: ignore[call-arg]
        _env_file=None,
        secret_key=CLAVE,
        database_url="sqlite+pysqlite:///:memory:",
        access_token_expire_minutes=30,
    )


@pytest.fixture
def repo_con_usuario(repo_usuarios_falso: RepositorioUsuariosFalso) -> RepositorioUsuariosFalso:
    repo_usuarios_falso.crear("disenador@example.com", "$2b$12$hash")
    return repo_usuarios_falso


def test_devuelve_el_usuario_del_token(
    repo_con_usuario: RepositorioUsuariosFalso, configuracion: Configuracion
) -> None:
    token = crear_token_de_acceso("1", CLAVE, minutos_de_expiracion=30)

    usuario = get_current_user(token=token, repo=repo_con_usuario, configuracion=configuracion)

    assert usuario.id == 1
    assert usuario.email == "disenador@example.com"


def test_token_invalido_da_401(
    repo_con_usuario: RepositorioUsuariosFalso, configuracion: Configuracion
) -> None:
    with pytest.raises(HTTPException) as error:
        get_current_user(token="no-es-un-token", repo=repo_con_usuario, configuracion=configuracion)

    assert error.value.status_code == 401


def test_token_de_otra_clave_da_401(
    repo_con_usuario: RepositorioUsuariosFalso, configuracion: Configuracion
) -> None:
    ajeno = crear_token_de_acceso("1", "otra-clave", minutos_de_expiracion=30)

    with pytest.raises(HTTPException) as error:
        get_current_user(token=ajeno, repo=repo_con_usuario, configuracion=configuracion)

    assert error.value.status_code == 401


def test_token_de_usuario_inexistente_da_401(
    repo_usuarios_falso: RepositorioUsuariosFalso, configuracion: Configuracion
) -> None:
    """Token bien firmado pero cuyo usuario ya no está: 401, nunca un usuario por defecto."""
    token = crear_token_de_acceso("999", CLAVE, minutos_de_expiracion=30)

    with pytest.raises(HTTPException) as error:
        get_current_user(token=token, repo=repo_usuarios_falso, configuracion=configuracion)

    assert error.value.status_code == 401


def test_sujeto_no_numerico_da_401(
    repo_con_usuario: RepositorioUsuariosFalso, configuracion: Configuracion
) -> None:
    token = crear_token_de_acceso("disenador@example.com", CLAVE, minutos_de_expiracion=30)

    with pytest.raises(HTTPException) as error:
        get_current_user(token=token, repo=repo_con_usuario, configuracion=configuracion)

    assert error.value.status_code == 401


def test_get_current_user_no_acepta_identidad_por_ningun_otro_canal() -> None:
    """Artículo IV.4: sus parámetros son token, repositorio y configuración. Nada más."""
    parametros = set(inspeccion.signature(get_current_user).parameters)

    assert parametros == {"token", "repo", "configuracion"}
    assert "usuario_id" not in parametros


def test_ninguna_dependencia_lee_un_usuario_id_de_la_peticion() -> None:
    """Ni de la ruta, ni del cuerpo, ni de un query param (Artículo IV.4)."""
    import app.dependencies as modulo

    arbol = ast.parse(inspeccion.getsource(modulo))
    nombres_de_parametros = {
        argumento.arg
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.FunctionDef)
        for argumento in nodo.args.args
    }

    assert "usuario_id" not in nombres_de_parametros

    fuente = inspeccion.getsource(modulo)
    for prohibido in ("Query(", "Path(", "Body("):
        assert prohibido not in fuente, f"las dependencias no deben leer identidad con {prohibido}"


def test_los_repositorios_se_ligan_a_la_sesion_de_la_peticion(sesion) -> None:  # noqa: ANN001
    assert isinstance(get_usuarios_repo(sesion), RepositorioUsuarios)
    assert isinstance(get_pistas_repo(sesion), RepositorioPistas)


def test_get_db_es_un_generador() -> None:
    """Artículo VII.5: es la dependencia que los tests de API sustituyen."""
    assert inspeccion.isgeneratorfunction(get_db)
