"""Tests de la identidad en sesiones MCP (Artículos VI.4 y IV.4).

Lo que se fija aquí es la regla del Artículo VI.4: con token verificado se usa ese
usuario; sin token se usa el demo como fallback documentado; y un token inválido **no**
degrada al demo, porque eso convertiría una credencial rechazada en acceso concedido.
"""

import ast
import inspect as inspeccion

import pytest

from app.mcp.auth import (
    EMAIL_USUARIO_DEMO,
    IdentidadNoDisponible,
    resolver_identidad,
)
from app.utils.seguridad import crear_token_de_acceso
from tests.fakes import RepositorioUsuariosFalso

CLAVE = "clave-de-prueba"


@pytest.fixture
def repo_con_usuario(repo_usuarios_falso: RepositorioUsuariosFalso) -> RepositorioUsuariosFalso:
    repo_usuarios_falso.crear("disenador@example.com", "$2b$12$hash")
    return repo_usuarios_falso


def test_con_token_verificado_usa_ese_usuario(
    repo_con_usuario: RepositorioUsuariosFalso,
) -> None:
    token = crear_token_de_acceso("1", CLAVE, minutos_de_expiracion=30)

    identidad = resolver_identidad(token=token, repo=repo_con_usuario, clave_secreta=CLAVE)

    assert identidad.usuario_id == 1
    assert identidad.email == "disenador@example.com"
    assert identidad.es_demo is False


def test_sin_token_cae_al_usuario_demo(repo_usuarios_falso: RepositorioUsuariosFalso) -> None:
    """Fallback legítimo del Artículo VI.4 para `stdio` sin identidad propagable."""
    identidad = resolver_identidad(token=None, repo=repo_usuarios_falso, clave_secreta=CLAVE)

    assert identidad.email == EMAIL_USUARIO_DEMO
    assert identidad.es_demo is True


def test_el_usuario_demo_se_reutiliza_no_se_duplica(
    repo_usuarios_falso: RepositorioUsuariosFalso,
) -> None:
    primera = resolver_identidad(token=None, repo=repo_usuarios_falso, clave_secreta=CLAVE)
    segunda = resolver_identidad(token=None, repo=repo_usuarios_falso, clave_secreta=CLAVE)

    assert primera.usuario_id == segunda.usuario_id
    assert len(repo_usuarios_falso.usuarios) == 1


def test_token_invalido_no_degrada_al_demo(
    repo_con_usuario: RepositorioUsuariosFalso,
) -> None:
    """Un token rechazado es un error, no una invitación a operar como demo."""
    with pytest.raises(IdentidadNoDisponible):
        resolver_identidad(token="no-es-un-token", repo=repo_con_usuario, clave_secreta=CLAVE)


def test_token_de_otra_clave_no_degrada_al_demo(
    repo_con_usuario: RepositorioUsuariosFalso,
) -> None:
    ajeno = crear_token_de_acceso("1", "otra-clave", minutos_de_expiracion=30)

    with pytest.raises(IdentidadNoDisponible):
        resolver_identidad(token=ajeno, repo=repo_con_usuario, clave_secreta=CLAVE)


def test_token_de_usuario_inexistente_falla(
    repo_usuarios_falso: RepositorioUsuariosFalso,
) -> None:
    token = crear_token_de_acceso("999", CLAVE, minutos_de_expiracion=30)

    with pytest.raises(IdentidadNoDisponible):
        resolver_identidad(token=token, repo=repo_usuarios_falso, clave_secreta=CLAVE)


def test_resolver_identidad_no_acepta_un_usuario_id_como_argumento() -> None:
    """Artículo IV.4: la identidad no se pasa por parámetro, se deriva del token."""
    parametros = set(inspeccion.signature(resolver_identidad).parameters)

    assert parametros == {"token", "repo", "clave_secreta"}
    assert "usuario_id" not in parametros


def test_el_fallback_demo_esta_documentado_en_el_codigo() -> None:
    """Artículo VI.4: la simplificación debe ser explícita, no un olvido silencioso."""
    import app.mcp.auth as modulo

    fuente = inspeccion.getsource(modulo)

    assert "simplificación consciente" in fuente
    assert "fallback" in fuente.lower()
    assert "Artículo VI.4" in fuente


def test_usa_la_misma_funcion_de_token_que_rest() -> None:
    """Artículo VI.4: el JWT de MCP es el mismo que el de REST, no un esquema paralelo."""
    import app.mcp.auth as modulo

    arbol = ast.parse(inspeccion.getsource(modulo))
    importados = {
        nodo.module
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.ImportFrom) and nodo.module
    }

    assert "app.utils.seguridad" in importados


def test_el_servidor_mcp_se_construye_y_no_tiene_reglas_de_negocio() -> None:
    """Artículo VI.1: el servidor solo registra tools; las reglas están en services."""
    from app.mcp.server import crear_servidor_mcp

    servidor = crear_servidor_mcp()
    assert servidor.name == "verificador-pistas-ipc2221"

    import app.mcp.server as modulo

    # Se inspeccionan identificadores usados, no el texto: nombrar una tool en el
    # docstring no es implementar su lógica.
    arbol = ast.parse(inspeccion.getsource(modulo))
    identificadores = {
        nodo.id for nodo in ast.walk(arbol) if isinstance(nodo, ast.Name)
    } | {nodo.attr for nodo in ast.walk(arbol) if isinstance(nodo, ast.Attribute)}
    importados = {
        nodo.module
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.ImportFrom) and nodo.module
    }

    for prohibido in ("ancho_minimo_mm", "TOLERANCIA_MM", "K_POR_CAPA"):
        assert prohibido not in identificadores
    assert "app.utils.ipc2221" not in importados


def test_la_app_monta_el_servidor_mcp() -> None:
    from app.main import RUTA_MCP, crear_app

    rutas_montadas = [
        getattr(ruta, "path", None) for ruta in crear_app().routes  # type: ignore[attr-defined]
    ]

    assert RUTA_MCP in rutas_montadas


# --- Lectura del token del transporte HTTP (Artículo VI.4) ---------------------------


def test_el_token_se_lee_pidiendo_explicitamente_la_cabecera_authorization() -> None:
    """FastMCP descarta `authorization` por defecto; hay que pedirla.

    Sin `include={"authorization"}`, `get_http_headers()` devuelve las cabeceras **sin** la
    credencial, la tool no ve token y la sesión cae al usuario demo aunque el cliente se
    haya autenticado. Eso incumpliría el Artículo VI.4, que obliga a usar la identidad del
    token cuando existe. Este test fija la llamada correcta.
    """
    import ast
    import inspect as inspeccion

    import app.mcp.tools.pistas as modulo

    arbol = ast.parse(inspeccion.getsource(modulo.token_de_la_sesion))
    llamadas = [
        nodo
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Call)
        and isinstance(nodo.func, ast.Name)
        and nodo.func.id == "get_http_headers"
    ]

    assert llamadas, "token_de_la_sesion debe consultar las cabeceras del transporte"
    argumentos = {kw.arg for llamada in llamadas for kw in llamada.keywords}
    assert "include" in argumentos or "include_all" in argumentos, (
        "get_http_headers descarta authorization por defecto: hay que pedirla explícitamente"
    )


def test_extrae_el_token_de_una_cabecera_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Con cabecera presente, se devuelve el token sin el prefijo `Bearer`."""
    import fastmcp.server.dependencies as dependencias

    from app.mcp.tools.pistas import token_de_la_sesion

    monkeypatch.setattr(
        dependencias,
        "get_http_headers",
        lambda **_: {"authorization": "Bearer abc.def.ghi"},
    )

    assert token_de_la_sesion() == "abc.def.ghi"


@pytest.mark.parametrize(
    "cabeceras",
    [{}, {"authorization": ""}, {"authorization": "Basic dXNlcjpwYXNz"}, {"otra": "x"}],
)
def test_sin_cabecera_bearer_no_hay_token(
    monkeypatch: pytest.MonkeyPatch, cabeceras: dict[str, str]
) -> None:
    """Sin credencial utilizable se devuelve None, que lleva al fallback documentado."""
    import fastmcp.server.dependencies as dependencias

    from app.mcp.tools.pistas import token_de_la_sesion

    monkeypatch.setattr(dependencias, "get_http_headers", lambda **_: cabeceras)

    assert token_de_la_sesion() is None
