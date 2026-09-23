"""Tests de las tools MCP.

Artículo VII.6: cada tool tiene como mínimo un caso exitoso y un caso de error de
negocio.
Artículo VI.1: se verifica además que la tool llama al **mismo** service que el router y
que no reimplementa ninguna regla.
"""

import ast
import asyncio
import inspect as inspeccion

import pytest

from app.mcp.auth import EMAIL_USUARIO_DEMO
from app.mcp.tools.pistas import (
    DESCRIPCION_REGISTRAR_PISTA,
    registrar_pista,
)
from app.utils.seguridad import crear_token_de_acceso
from tests.fakes import RepositorioPistasFalso, RepositorioUsuariosFalso

CLAVE_DE_PRUEBA = "clave-de-prueba-solo-para-tests"

ARGUMENTOS_VALIDOS = {
    "nombre_red": "VBUS",
    "proyecto": "fuente-5v",
    "corriente_a": 1.0,
    "espesor_oz": 1.0,
    "capa": "externa",
    "delta_t_c": 10.0,
    "ancho_mm": 0.5,
}


def _con(**cambios: object) -> dict[str, object]:
    argumentos = dict(ARGUMENTOS_VALIDOS)
    argumentos.update(cambios)
    return argumentos


# --- registrar_pista: caso exitoso y casos de error (Artículo VII.6) -----------------


def test_registrar_pista_exitoso_devuelve_la_pista(
    repo_pistas_falso: RepositorioPistasFalso,
    repo_usuarios_falso: RepositorioUsuariosFalso,
) -> None:
    resultado = registrar_pista(
        **_con(), repo=repo_pistas_falso, repo_usuarios=repo_usuarios_falso
    )

    assert "error" not in resultado
    assert resultado["pista"]["nombre_red"] == "VBUS"
    assert resultado["pista"]["capa"] == "externa"
    assert repo_pistas_falso.escrituras == ["guardar"]


def test_registrar_pista_con_ancho_insuficiente_devuelve_estructura_de_error(
    repo_pistas_falso: RepositorioPistasFalso,
    repo_usuarios_falso: RepositorioUsuariosFalso,
) -> None:
    """Artículo VI.3: error de negocio como `{"error": ...}`, no excepción sin controlar."""
    resultado = registrar_pista(
        **_con(ancho_mm=0.1), repo=repo_pistas_falso, repo_usuarios=repo_usuarios_falso
    )

    assert "IPC-2221" in resultado["error"]
    assert repo_pistas_falso.escrituras == []


def test_registrar_pista_fuera_de_rango_devuelve_error(
    repo_pistas_falso: RepositorioPistasFalso,
    repo_usuarios_falso: RepositorioUsuariosFalso,
) -> None:
    resultado = registrar_pista(
        **_con(corriente_a=36.0, ancho_mm=50.0),
        repo=repo_pistas_falso,
        repo_usuarios=repo_usuarios_falso,
    )

    assert "rango de validez" in resultado["error"]


def test_registrar_pista_con_capa_invalida_devuelve_error_no_excepcion(
    repo_pistas_falso: RepositorioPistasFalso,
    repo_usuarios_falso: RepositorioUsuariosFalso,
) -> None:
    """El equivalente del 422 de REST, devuelto como estructura."""
    resultado = registrar_pista(
        **_con(capa="superficial"), repo=repo_pistas_falso, repo_usuarios=repo_usuarios_falso
    )

    assert "datos inválidos" in resultado["error"]
    assert repo_pistas_falso.escrituras == []


# --- Identidad (Artículos VI.4 y IV.4) ----------------------------------------------


def test_sin_token_opera_como_usuario_demo_y_lo_declara(
    repo_pistas_falso: RepositorioPistasFalso,
    repo_usuarios_falso: RepositorioUsuariosFalso,
) -> None:
    resultado = registrar_pista(
        **_con(), repo=repo_pistas_falso, repo_usuarios=repo_usuarios_falso
    )

    assert resultado["usuario_demo"] is True
    assert repo_usuarios_falso.obtener_por_email(EMAIL_USUARIO_DEMO) is not None


def test_con_token_valido_opera_como_ese_usuario(
    repo_pistas_falso: RepositorioPistasFalso,
    repo_usuarios_falso: RepositorioUsuariosFalso,
) -> None:
    usuario = repo_usuarios_falso.crear("disenador@example.com", "$2b$12$hash")
    token = crear_token_de_acceso(str(usuario.id), CLAVE_DE_PRUEBA, minutos_de_expiracion=30)

    resultado = registrar_pista(
        **_con(), token=token, repo=repo_pistas_falso, repo_usuarios=repo_usuarios_falso
    )

    assert resultado["usuario_demo"] is False
    assert repo_pistas_falso.pistas[1].usuario_id == usuario.id


def test_con_token_invalido_devuelve_error_y_no_cae_al_demo(
    repo_pistas_falso: RepositorioPistasFalso,
    repo_usuarios_falso: RepositorioUsuariosFalso,
) -> None:
    resultado = registrar_pista(
        **_con(), token="no-es-un-token", repo=repo_pistas_falso, repo_usuarios=repo_usuarios_falso
    )

    assert "error" in resultado
    assert repo_pistas_falso.escrituras == []
    assert repo_usuarios_falso.obtener_por_email(EMAIL_USUARIO_DEMO) is None


def test_la_tool_expuesta_no_acepta_usuario_id_ni_token() -> None:
    """Artículo IV.4: la identidad no se pide al cliente MCP."""
    from fastmcp import FastMCP

    from app.mcp.tools.pistas import registrar_tools

    servidor = registrar_tools(FastMCP(name="prueba"))
    tool = asyncio.run(servidor.get_tool("registrar_pista"))

    assert tool is not None
    parametros = set(inspeccion.signature(tool.fn).parameters)
    assert parametros == {
        "nombre_red",
        "proyecto",
        "corriente_a",
        "espesor_oz",
        "capa",
        "delta_t_c",
        "ancho_mm",
    }
    assert "usuario_id" not in parametros
    assert "token" not in parametros


# --- Registro y descripción ---------------------------------------------------------


def test_la_tool_esta_registrada_en_el_servidor() -> None:
    from app.mcp.server import crear_servidor_mcp

    servidor = crear_servidor_mcp()
    tools = asyncio.run(servidor.list_tools())

    assert "registrar_pista" in {tool.name for tool in tools}


def test_la_descripcion_es_especifica_y_verificable() -> None:
    """Artículo VI.2: nunca genérica como "maneja pistas"."""
    from app.mcp.server import crear_servidor_mcp

    servidor = crear_servidor_mcp()
    tool = asyncio.run(servidor.get_tool("registrar_pista"))

    assert tool is not None
    assert tool.description == DESCRIPCION_REGISTRAR_PISTA
    assert "IPC-2221" in tool.description
    assert "rechaza" in tool.description
    assert len(tool.description) > 80


# --- Reutilización: la tool no reimplementa el service (Artículo VI.1) --------------


def test_la_tool_llama_al_mismo_service_que_el_router() -> None:
    import app.mcp.tools.pistas as modulo_tool
    import app.routers.pistas as modulo_router

    def _importados(modulo: object) -> set[str]:
        arbol = ast.parse(inspeccion.getsource(modulo))  # type: ignore[arg-type]
        nombres: set[str] = set()
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.ImportFrom) and nodo.module:
                nombres.add(nodo.module)
        return nombres

    assert "app.services" in _importados(modulo_tool)
    assert "app.services" in _importados(modulo_router)


def test_la_tool_no_reimplementa_ninguna_regla() -> None:
    """Sin cálculo, sin tolerancia y sin constantes de la norma en la capa de tools."""
    import app.mcp.tools.pistas as modulo

    fuente = inspeccion.getsource(modulo)

    for prohibido in ("ancho_minimo_mm", "TOLERANCIA_MM", "K_POR_CAPA", "0.048", "0.001", "35.0"):
        assert prohibido not in fuente


def test_el_token_de_la_sesion_es_none_fuera_de_contexto_http() -> None:
    """Transporte `stdio`: no hay cabeceras, así que no hay token (Artículo VI.4)."""
    from app.mcp.tools.pistas import token_de_la_sesion

    assert token_de_la_sesion() is None


def test_no_se_usa_unittest_mock_en_este_archivo() -> None:
    """Artículo VII.2."""
    arbol = ast.parse(open(__file__, encoding="utf-8").read())
    importados = {
        nodo.module
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.ImportFrom) and nodo.module
    }

    assert not any(nombre.startswith("unittest") for nombre in importados)


@pytest.mark.parametrize("campo", ["nombre_red", "proyecto"])
def test_texto_vacio_devuelve_error_de_datos(
    repo_pistas_falso: RepositorioPistasFalso,
    repo_usuarios_falso: RepositorioUsuariosFalso,
    campo: str,
) -> None:
    resultado = registrar_pista(
        **_con(**{campo: ""}), repo=repo_pistas_falso, repo_usuarios=repo_usuarios_falso
    )

    assert "datos inválidos" in resultado["error"]
